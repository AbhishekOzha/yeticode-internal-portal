"""The catalog of units, roles and capabilities, and each role's default capabilities.

This is the single source of truth used to seed the database. After seeding,
Super Admins can change a role's capabilities in the Django admin; seeding
never overwrites a role that already exists.
"""

# Capability codename -> (label, dashboard widget description).
# Each capability becomes a Django permission "accounts.<codename>".
CAPABILITIES = {
    # Shared
    "view_unit_directory": ("Unit directory", "See the people in your unit and their roles."),
    "manage_unit_users": ("User management", "Add, edit and deactivate accounts in your unit."),
    # Web App Development
    "view_projects": ("Projects", "Browse the unit's active client projects."),
    "work_on_tasks": ("My tasks", "Track the development tasks assigned to you."),
    "review_code": ("Code reviews", "Review pull requests from other developers."),
    "assign_tasks": ("Task assignment", "Assign and prioritise tasks across the team."),
    "manage_dev_team": ("Team overview", "Monitor workload and progress of your developers."),
    # Training
    "view_courses": ("Courses", "Browse the courses offered by the training unit."),
    "view_own_progress": ("My progress", "Your enrolled courses, attendance and grades."),
    "teach_classes": ("My classes", "Your class schedule and batches you teach."),
    "grade_students": ("Grading", "Record assessments and grades for your students."),
    "manage_enquiries": ("Enquiries", "Log and follow up walk-in and phone enquiries."),
    "manage_enrollments": ("Enrollments", "Enroll students into courses and batches."),
    "manage_batches": ("Batches", "Plan batches and assign instructors."),
    "view_training_reports": ("Training reports", "Enrollment, attendance and result reports."),
    # Academic Content Writing
    "write_content": ("My assignments", "Writing assignments assigned to you and their deadlines."),
    "conduct_research": ("Research", "Research briefs and sources for your assignments."),
    "review_content": ("Quality review", "Review submitted drafts before delivery."),
    "manage_production": ("Production pipeline", "Assign orders to writers and track delivery."),
    "manage_leads": ("Leads & orders", "Track client leads and incoming orders."),
    "view_sales_reports": ("Sales reports", "Revenue and conversion reports for the sales team."),
    "manage_sales_team": ("Sales team", "Targets and performance of sales executives."),
    "manage_employee_records": ("Employee records", "Staff records, onboarding and leave."),
    # Company-wide (only for roles that are not tied to a unit)
    "view_all_employee_records": (
        "Company-wide employee records",
        "Everyone employed across all three units, with their unit and role.",
    ),
}

# Capabilities that reach across units. Only company-wide roles (roles with no
# unit) may hold them, so unit-scoped roles stay isolated from other units.
CROSS_UNIT_CAPABILITIES = {"view_all_employee_records"}

WEB = "web"
TRAINING = "training"
CONTENT = "content"
COMPANY_WIDE = None  # Role is not tied to any unit.

UNITS = {
    WEB: "Web App Development",
    TRAINING: "Training",
    CONTENT: "Academic Content Writing",
}

# (unit, role code, role name, rank within unit, default capabilities)
# A unit of COMPANY_WIDE makes a role that is not tied to any single unit.
# Rank orders roles from most junior (1) upwards; it is informational.
ROLES = [
    (WEB, "junior_web_developer", "Junior Web Developer", 1,
     ["view_unit_directory", "view_projects", "work_on_tasks"]),
    (WEB, "web_developer", "Web Developer", 2,
     ["view_unit_directory", "view_projects", "work_on_tasks"]),
    (WEB, "senior_web_developer", "Senior Web Developer", 3,
     ["view_unit_directory", "view_projects", "work_on_tasks", "review_code"]),
    (WEB, "team_lead", "Team Lead", 4,
     ["view_unit_directory", "view_projects", "work_on_tasks", "review_code",
      "assign_tasks", "manage_dev_team", "manage_unit_users"]),

    (TRAINING, "student", "Student", 1,
     ["view_unit_directory", "view_courses", "view_own_progress"]),
    (TRAINING, "instructor", "Instructor", 2,
     ["view_unit_directory", "view_courses", "teach_classes", "grade_students"]),
    (TRAINING, "front_desk_coordinator", "Front Desk Coordinator", 2,
     ["view_unit_directory", "view_courses", "manage_enquiries", "manage_enrollments"]),
    (TRAINING, "training_manager", "Training Manager", 3,
     ["view_unit_directory", "view_courses", "manage_enquiries", "manage_enrollments",
      "manage_batches", "view_training_reports", "manage_unit_users"]),

    (CONTENT, "content_writer", "Content Writer", 1,
     ["view_unit_directory", "write_content"]),
    (CONTENT, "content_writer_research_specialist", "Content Writer & Research Specialist", 2,
     ["view_unit_directory", "write_content", "conduct_research"]),
    (CONTENT, "production_manager", "Production Manager", 3,
     ["view_unit_directory", "review_content", "manage_production", "manage_unit_users"]),
    (CONTENT, "sales_executive", "Sales Executive", 1,
     ["view_unit_directory", "manage_leads"]),
    (CONTENT, "sales_manager", "Sales Manager", 2,
     ["view_unit_directory", "manage_leads", "view_sales_reports", "manage_sales_team"]),
    (CONTENT, "hr", "HR", 2,
     ["view_unit_directory", "manage_employee_records"]),

    (COMPANY_WIDE, "head_hr", "Head HR", 1,
     ["manage_employee_records", "view_all_employee_records"]),
]

# Each unit's admin is its most senior role, which also holds manage_unit_users
# (accounts in its own unit only). `create_default_users` makes one account per
# unit with that role: (username, role code). No unit admin can use the
# Django admin panel.
UNIT_ADMINS = {
    WEB: ("web_admin", "team_lead"),
    TRAINING: ("training_admin", "training_manager"),
    CONTENT: ("content_admin", "production_manager"),
}
