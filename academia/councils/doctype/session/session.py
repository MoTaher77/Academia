# Copyright (c) 2024, SanU and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate

class Session(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from academia.councils.doctype.session_member.session_member import SessionMember
        from academia.councils.doctype.session_topic_assignment.session_topic_assignment import SessionTopicAssignment
        from frappe.types import DF

        amended_from: DF.Link | None
        begin_time: DF.Time | None
        council: DF.Link
        date: DF.Date | None
        end_time: DF.Time | None
        members: DF.Table[SessionMember]
        naming_series: DF.Literal["CNCL-SESS-.YY.-.{council}.-.###"]
        opening: DF.Text
        title: DF.Data
        topics: DF.Table[SessionTopicAssignment]
    # end: auto-generated types

    def detect_assignments_changes(self):
        """
        This function compares the current session's assignments with the previous session's assignments,
        and returns a list of edited assignments, a list of added assignments, and a list of deleted assignments.

        Returns:
            tuple: A tuple containing three lists: edited assignments, added assignments, and deleted assignments.

        """
        # Check if this is a new session (no previous session to compare with)
        if self.is_new():
            return None, None, None

        # Get the previous session's assignments
        old_session = self.get_doc_before_save()
        old_assignments = {
            row.name: row for row in old_session.assignments} if old_session else {}

        # Get the current session's assignments as dictionary and set name as key
        current_assignments = {row.name: row for row in self.assignments}

        # Find deleted assignments (assignments present in old session but not in current session)
        deleted_assignments = [
            row for row in old_session.assignments if row.name not in current_assignments]

        # Find added assignments (assignments present in current session but marked as new)
        added_assignments = [row for row in self.assignments if row.is_new()]

        # Initialize a list to store edited assignments
        edited_assignments = []

        # Iterate through the current session's assignments
        for row_name, assignment_doc in current_assignments.items():
            # Check if the assignment exists in the old session and is not marked as new
            if row_name in old_assignments and not assignment_doc.is_new():
                # Get the old assignment document
                old_assignment_doc = old_assignments[row_name]

                # Compare the modified status of the old and current assignments
                if old_assignment_doc.modified != assignment_doc.modified:
                    # If the modified status is different, add the assignment to the edited assignments list
                    edited_assignments.append(assignment_doc)

        # Return the lists of edited, added, and deleted assignments
        return edited_assignments, added_assignments, deleted_assignments

    def before_save(self):
        self.update_forward_assignments_status()
        
    def update_forward_assignments_status(self):
        """
        This function updates the status of the forward assignments of a session.

        Args:
            self (Session): The current session document.

        Returns:
            None

        """
        # Detect changes in assignments (edited or added)
        edited_assignments, added_assignments, _ = self.detect_assignments_changes()

        # Combine edited and added assignments into a single list
        changed_assignments = edited_assignments + added_assignments

        # Iterate through the changed assignments
        for assignment in changed_assignments:
            # Check if the decision type of the assignment is "Transferred"
            if assignment.decision_type == "Transferred":
                # Get the old status of the forward assignment
                old_status = frappe.get_value(
                    "Topic Assignment", assignment.forward_assignment, "status")

                # If the old status is not "Pending Review", update the status to "Pending Review"
                if old_status != "Pending Review":
                    frappe.db.set_value(
                        "Topic Assignment", assignment.forward_assignment, "status", "Pending Review")

    def create_postponed_assignment(self, session_assignment):
        """Creates a new Topic Assignment with postponed status the specified details.
        
        Args:
                session_assignment (Session.assignments): The session assignment details.
        Returns:
                Document: The newly created Topic Assignment document.
        """
        doc_assignment = frappe.new_doc("Topic Assignment")
        doc_assignment.title = session_assignment.title
        doc_assignment.description = session_assignment.description
        doc_assignment.assignment_date = nowdate(),
        doc_assignment.council = session_assignment.council
        doc_assignment.topic = session_assignment.topic
        doc_assignment.status = "Accepted"
        doc_assignment.insert()
        return doc_assignment

    
    def on_submit(self):
        self.process_session_assignments()
        
    def process_session_assignments(self):
        """
        Process each session assignment, create new assignments for postponed topics,
        and update existing topic assignments with decision details.
        """
        # Retrieve session assignments from the document
        session_assignments = self.assignments

        # Process each session assignment
        for session_assignment in session_assignments:
            # Retrieve details of the corresponding Topic Assignment
            session_assignment_doc = frappe.get_doc(
                "Topic Assignment", session_assignment.topic_assignment)

            # If the decision type is "Postponed":
            if session_assignment.decision_type == "Postponed":
                # Create a new assignment for postponed topics
                if session_assignment_doc:
                    doc_assignment = self.create_postponed_assignment(session_assignment)
                    session_assignment.forward_assignment = doc_assignment.name  # Link the new assignment

            # Update the Topic Assignment with the decision details
            session_assignment_doc.decision = session_assignment.decision
            session_assignment_doc.decision_type = session_assignment.decision_type
            session_assignment_doc.save()
            session_assignment_doc.submit()
