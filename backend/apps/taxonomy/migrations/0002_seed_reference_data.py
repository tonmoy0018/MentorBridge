"""
Seeds neutral reference data (career areas, professions, skills, languages).
This is vocabulary for profiles and search, not customer data. Idempotent.
"""

from django.db import migrations
from django.utils.text import slugify

CATEGORIES = [
    ("Technology", "Software, data, product and IT careers."),
    ("Finance", "Banking, investment, accounting and corporate finance."),
    ("Healthcare", "Clinical, research and health-industry careers."),
    ("Design", "Product, UX, visual and service design."),
    ("Consulting", "Management, strategy and specialist consulting."),
    ("Marketing", "Brand, growth, content and communications."),
    ("Engineering", "Mechanical, electrical, civil and other engineering disciplines."),
    ("Law", "Legal practice, compliance and policy."),
    ("Human Resources", "Recruiting, people operations and talent development."),
    ("Education", "Teaching, academia and learning design."),
    ("Public Sector", "Government, policy and non-profit careers."),
]

PROFESSIONS = [
    ("Product Manager", "Technology"),
    ("Software Engineer", "Technology"),
    ("Data Scientist", "Technology"),
    ("Data Analyst", "Technology"),
    ("Security Engineer", "Technology"),
    ("Investment Banker", "Finance"),
    ("Accountant", "Finance"),
    ("Financial Analyst", "Finance"),
    ("Clinical Researcher", "Healthcare"),
    ("Physician", "Healthcare"),
    ("Product Designer", "Design"),
    ("UX Researcher", "Design"),
    ("Management Consultant", "Consulting"),
    ("Marketing Manager", "Marketing"),
    ("Mechanical Engineer", "Engineering"),
    ("Civil Engineer", "Engineering"),
    ("Lawyer", "Law"),
    ("Recruiter", "Human Resources"),
    ("Teacher", "Education"),
    ("Policy Analyst", "Public Sector"),
]

SKILLS = [
    "Product strategy", "User research", "Roadmapping", "Stakeholder management", "System design",
    "Backend development", "Frontend development", "Technical interviews", "Career growth", "Machine learning",
    "Python", "SQL", "Statistics", "Financial modelling", "Valuation", "Interview preparation", "UX design",
    "Portfolio review", "Design systems", "Case interviews", "Problem solving", "Presentation skills",
    "Brand strategy", "Growth marketing", "Content strategy", "Robotics", "CAD", "Leadership",
    "Clinical trials", "Regulatory affairs", "Career transitions", "Contract law", "Law school applications",
    "Resume review", "Salary negotiation", "Cybersecurity", "Cloud architecture", "Certifications",
    "Public speaking", "Networking",
]

LANGUAGES = [
    ("ar", "Arabic"), ("bn", "Bengali"), ("de", "German"), ("en", "English"), ("es", "Spanish"),
    ("fr", "French"), ("hi", "Hindi"), ("id", "Indonesian"), ("it", "Italian"), ("ja", "Japanese"),
    ("ko", "Korean"), ("ml", "Malayalam"), ("nl", "Dutch"), ("pl", "Polish"), ("pt", "Portuguese"),
    ("ru", "Russian"), ("sv", "Swedish"), ("sw", "Swahili"), ("ta", "Tamil"), ("tr", "Turkish"),
    ("tw", "Twi"), ("uk", "Ukrainian"), ("ur", "Urdu"), ("vi", "Vietnamese"), ("yo", "Yoruba"),
    ("zh", "Chinese"),
]


def seed(apps, schema_editor):
    Category = apps.get_model("taxonomy", "Category")
    Profession = apps.get_model("taxonomy", "Profession")
    Skill = apps.get_model("taxonomy", "Skill")
    Language = apps.get_model("taxonomy", "Language")

    by_name = {}
    for order, (name, description) in enumerate(CATEGORIES):
        category, _ = Category.objects.get_or_create(
            slug=slugify(name), defaults={"name": name, "description": description, "sort_order": order}
        )
        by_name[name] = category
    for name, category in PROFESSIONS:
        Profession.objects.get_or_create(slug=slugify(name), defaults={"name": name, "category": by_name[category]})
    for name in SKILLS:
        Skill.objects.get_or_create(slug=slugify(name), defaults={"name": name})
    for code, name in LANGUAGES:
        Language.objects.get_or_create(code=code, defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("taxonomy", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
