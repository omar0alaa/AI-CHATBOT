import sqlite3

# Connect (or create) the database file
conn = sqlite3.connect('youlearnt_bank.db')
cursor = conn.cursor()

# Create the table
cursor.execute('''
CREATE TABLE IF NOT EXISTS youlearnt_bank (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL
)
''')

# The verified Q&A data strictly from your input
youlearnt_bank = [
    ("What is YouLearnt?",
     "YouLearnt is a global online learning platform connecting learners with tutors and mentors through personalized real-time live courses."),
    ("What is the vision of YouLearnt?",
     "To be the world’s leading platform for personalised education, where every learner discovers exactly what they seek and fulfils their passion for knowledge."),
    ("What is the mission of YouLearnt?",
     "To bring people together globally to achieve educational goals by removing geographical barriers and providing accessible high-quality education."),
    ("What problems does YouLearnt solve?",
     "It removes access barriers by connecting learners and educators globally and helps institutions transition to online/hybrid models without building their own systems."),
    ("What are some key features of YouLearnt?",
     "Real-time live video lessons, 24/7 technical and customer support, comprehensive user dashboards, interactive blog and community forums, secure profile and wallet management."),
    ("What features does YouLearnt offer for tutors?",
     "Free profile creation and customization, dashboard with student and income insights, support for one-to-one and group classes, blog publishing, community Q&A, flexible pricing and commissions, course creation tools, and 'Find Students' features."),
    ("What features are available for students on YouLearnt?",
     "Search tutors with filters (subject, language, country, availability, price), save favorite tutors, downloadable certificates, wallet top-up, tutor requests, access group and one-to-one courses, transparent payment and class management."),
    ("What class types does YouLearnt offer?",
     "One-to-one lessons (trial and package lessons) and group courses with scheduled classes."),
    ("How does YouLearnt’s tutor commission work?",
     "Tutors create profiles for free. Commissions: 75% on first lesson with a new student (for advertising), 25% commission on package lessons after the trial, future lessons charged 25% commission reducing to 20% after 300 hours (Senior Tutor), and 15% after 1000 hours (Professional Tutor). Milestones allow custom profile URLs and increased visibility."),
    ("What is the B2C model in YouLearnt?",
     "Individual learners and tutors sign up free, get paid per session, with tiered commission and certificates."),
    ("What is the B2B model in YouLearnt?",
     "Organizations get free trials, revenue-sharing model with 20-30% income share, and support for hybrid/online transitions without new infrastructure."),
    ("How do you create an account on YouLearnt?",
     "Visit the YouLearnt website, register as a student or tutor, enter details, and verify email."),
    ("How do you log in?",
     "Click “Log In” and use registered credentials."),
    ("What are key navigation pages?",
     "My Classes, Payments, Certificates, Find Tutors, and Course Management."),
    ("What does the Tutor Dashboard include?",
     "Total students, hours taught, payments, scheduled lessons, notifications, profile views, scores, hourly rate, availability, cancellations, absences, active students."),
    ("What can tutors manage?",
     "Add/manage courses, view class summaries, chat with students, reschedule lessons, manage blog posts, answer community questions, track profile score, and use referral tools."),
    ("What is the blog on YouLearnt?",
     "Tutors can publish articles (800–1500 words) reviewed for quality, focusing on educational topics."),
    ("What is the community feature?",
     "Tutors and learners ask and answer questions; posts are reviewed before public release. Engagement boosts tutor profile scores."),
    ("How is support provided?",
     "24/7 through the Support Hub where users can raise assistance tickets."),
    ("How do referrals work?",
     "Each user gets a unique link to invite others and earn credit from first class booked by referrals."),
    ("What is the affiliate marketing program?",
     "Designed for social influencers, requires separate registration, and pays commissions based on user conversion."),
    ("How are courses conducted?",
     "All lessons are live and interactive via video conferencing."),
    ("Can institutions use YouLearnt?",
     "Yes. Schools, universities, and training centers can deliver online/hybrid classes with their own teachers."),
    ("How do students find tutors?",
     "Using filters on the Find Tutors page or by posting Tutor Requests."),
    ("What does the profile score mean?",
     "It reflects tutor activity, profile completeness, responsiveness, and engagement, improving visibility."),
    ("Can I teach or learn rare subjects?",
     "Yes. Students can add new subjects in tutor requests; tutors can request new subjects from the platform."),
    ("Are children allowed on YouLearnt?",
     "Yes. Parents can create and manage children’s accounts."),
    ("What is a trial session?",
     "The first one-to-one lesson at the tutor’s regular hourly rate."),
    ("What are packages?",
     "Bundles of lessons purchased after a trial session."),
    ("How do tutors set availability?",
     "Tutors control their schedule and can set availability up to 30 days in advance."),
    ("Can I switch between tutor and student roles?",
     "Yes, by clicking “Become a Student” or “Become a Tutor” buttons."),
    ("How do learners pay?",
     "Through wallet top-up with various payment options."),
    ("How do tutors withdraw earnings?",
     "Via PayPal, Wise, or Payoneer from the Finance page."),
    ("Where can I find YouLearnt’s policies?",
     "On the website at URLs for Privacy Policy, Security, Terms & Conditions, Cookies Policy, Pricing Policy, and FAQ pages."),
]

# Insert the Q&A pairs into the database
for question, answer in youlearnt_bank:
    cursor.execute('INSERT INTO youlearnt_bank (question, answer) VALUES (?, ?)', (question, answer))

# Save and close
conn.commit()
conn.close()

print("SQLite database 'youlearnt_bank.db' created with verified Q&A data.")
