"""
Local demo accounts for showing MentorBridge to people. Development only.

Every account is fictional and labelled "(Demo)", uses an @example.com address and has a
verified email. Mentors go through the real submit → approve workflow (approved by the demo
admin); one is left pending so the admin verification queue has something to review. No
bookings, payments or reviews are created: make those live during the demo.

Every session is paid (no free sessions). Demo mentors also get in-person options, multi-session
bundles and upcoming group seminars. Booking any of them needs payments in test mode
(docs/PAYMENTS.md §6); no payment is ever recorded by this command.

Additive and idempotent: existing accounts and records are never changed or deleted. Re-running
only adds demo services, bundles and upcoming seminars (matched by title, or session count for
bundles) that a demo mentor doesn't have yet.
"""

import os
import secrets
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import password_validation
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.common.exceptions import Conflict
from apps.mentors import services as mentor_services
from apps.mentors.models import MentorProfile
from apps.packages import services as package_services
from apps.seminars import services as seminar_services
from apps.seminars.models import SeminarStatus
from apps.students.models import StudentProfile
from apps.taxonomy.models import Category, Language, Profession, Skill
from apps.users.models import Role, User

DEMO_NOTE = "This is a fictional demo profile for showing MentorBridge. It is not a real person."

ADMIN = {"email": "demo.admin@example.com", "first_name": "Alex", "last_name": "Admin (Demo)"}

STUDENTS = [
    {
        "email": "demo.student@example.com",
        "first_name": "Sam",
        "last_name": "Taylor (Demo)",
        "headline": "Final-year computer science student",
        "country": "GB",
        "interests": ["Technology", "Design"],
    },
    {
        "email": "demo.student2@example.com",
        "first_name": "Nadia",
        "last_name": "Islam (Demo)",
        "headline": "Economics graduate exploring consulting",
        "country": "BD",
        "interests": ["Consulting", "Finance"],
    },
]

WEEKDAYS = range(5)

MENTORS = [
    {
        "email": "demo.mentor.product@example.com",
        "first_name": "Asha",
        "last_name": "Rahman (Demo)",
        "timezone": "Asia/Dhaka",
        "country": "BD",
        "headline": "Helping engineers and analysts move into product management",
        "title": "Senior Product Manager",
        "profession": "Product Manager",
        "years": 9,
        "categories": ["Technology"],
        "skills": ["Product strategy", "Roadmapping", "Stakeholder management", "Interview preparation"],
        "languages": ["en", "bn"],
        "services": [
            ("Intro call", "A short call to talk through your goals and how I can help.", 15, 1500),
            ("Product interview practice", "A mock product-sense interview with written feedback.", 60, 6000),
        ],
        "hours": [(day, time(10), time(17)) for day in WEEKDAYS],
    },
    {
        "email": "demo.mentor.engineering@example.com",
        "first_name": "Daniel",
        "last_name": "Okafor (Demo)",
        "timezone": "Europe/London",
        "country": "GB",
        "headline": "System design and backend interview preparation",
        "title": "Staff Software Engineer",
        "profession": "Software Engineer",
        "years": 12,
        "categories": ["Technology"],
        "skills": ["System design", "Backend development", "Technical interviews", "Python"],
        "languages": ["en"],
        "auto_accept": True,
        "services": [
            ("Career Q&A", "Ask anything about engineering careers, levels and growth.", 30, 3000),
            ("System design mock interview", "A realistic 60-minute system design round.", 60, 8000),
        ],
        "hours": [(day, time(9), time(13)) for day in WEEKDAYS] + [(5, time(10), time(12))],
    },
    {
        "email": "demo.mentor.design@example.com",
        "first_name": "Maria",
        "last_name": "Gonzalez (Demo)",
        "timezone": "Europe/Madrid",
        "country": "ES",
        "headline": "Portfolio reviews for junior and mid-level product designers",
        "title": "Lead Product Designer",
        "profession": "Product Designer",
        "years": 8,
        "categories": ["Design"],
        "skills": ["UX design", "Portfolio review", "Design systems"],
        "languages": ["en", "es"],
        "services": [
            ("Intro call", "Tell me where you are and where you want to go.", 15, 1500),
            ("Portfolio review", "A detailed walkthrough of your portfolio with next steps.", 45, 4500),
        ],
        "hours": [(day, time(14), time(19)) for day in WEEKDAYS],
    },
    {
        "email": "demo.mentor.data@example.com",
        "first_name": "Priya",
        "last_name": "Nair (Demo)",
        "timezone": "Asia/Kolkata",
        "country": "IN",
        "headline": "Breaking into data science and machine learning roles",
        "title": "Data Science Manager",
        "profession": "Data Scientist",
        "years": 10,
        "categories": ["Technology"],
        "skills": ["Machine learning", "Python", "SQL", "Statistics"],
        "languages": ["en", "hi", "ml"],
        "services": [
            ("Career Q&A", "Questions about data roles, skills and learning paths.", 30, 2500),
            ("Data science interview practice", "Statistics, SQL and ML case questions.", 60, 5000),
        ],
        "hours": [(day, time(18), time(21)) for day in WEEKDAYS],
    },
    {
        # Left pending so the admin's verification queue has a request to approve live.
        "email": "demo.mentor.consulting@example.com",
        "first_name": "Lukas",
        "last_name": "Weber (Demo)",
        "timezone": "Europe/Berlin",
        "country": "DE",
        "headline": "Case interview coaching for management consulting",
        "title": "Engagement Manager",
        "profession": "Management Consultant",
        "years": 7,
        "categories": ["Consulting"],
        "skills": ["Case interviews", "Problem solving", "Presentation skills"],
        "languages": ["en", "de"],
        "approve": False,
        "services": [
            ("Intro call", "A quick chat about consulting recruiting.", 30, 2500),
            ("Case interview practice", "A full case with structured feedback.", 60, 9000),
        ],
        "hours": [(day, time(8), time(12)) for day in WEEKDAYS],
    },
]


# Added to demo mentors (new or existing) when missing, matched by title.
OFFERINGS = {
    "demo.mentor.product@example.com": {
        "services": [
            {
                "title": "Career strategy session",
                "description": "Plan your next career move, online or over coffee.",
                "duration_minutes": 45,
                "price_cents": 4000,
                "in_person": True,
                "in_person_extra_cents": 1500,
                "in_person_area": "Gulshan or Banani, Dhaka (public cafés)",
            },
        ],
        "packages": [
            {
                "service": "Product interview practice",
                "session_count": 3,
                "discount_percent": 15,
                "validity_days": 45,
            },
        ],
        "seminars": [
            {
                "service": "Product interview practice",
                "title": "Group product interview practice",
                "description": "Practise product-sense answers together, with feedback for everyone.",
                "days_ahead": 7,
                "local_time": time(19),
                "duration_minutes": 90,
                "capacity": 8,
                "price_cents": 2000,
            },
        ],
    },
    "demo.mentor.engineering@example.com": {
        "services": [
            {
                "title": "Coffee chat",
                "description": "An informal chat about engineering careers, online or in person.",
                "duration_minutes": 30,
                "price_cents": 3000,
                "in_person_extra_cents": 500,
                "in_person": True,
                "in_person_area": "Shoreditch, London",
            },
        ],
        "packages": [
            {
                "service": "Career Q&A",
                "session_count": 3,
                "discount_percent": 10,
                "validity_days": 30,
            },
        ],
        "seminars": [
            {
                "service": "Career Q&A",
                "title": "Open Q&A: your first engineering job",
                "description": "Bring your questions about applications, interviews and first roles.",
                "days_ahead": 5,
                "local_time": time(18),
                "duration_minutes": 60,
                "capacity": 12,
                "price_cents": 1000,
            },
        ],
    },
    "demo.mentor.design@example.com": {
        "services": [
            {
                "title": "Design critique",
                "description": "Bring a project and we'll review it together.",
                "duration_minutes": 60,
                "price_cents": 5000,
                "in_person": True,
                "in_person_extra_cents": 2000,
                "in_person_area": "Malasaña, Madrid",
            },
        ],
        "packages": [
            {
                "service": "Portfolio review",
                "session_count": 3,
                "discount_percent": 10,
                "validity_days": 60,
            },
        ],
        "seminars": [
            {
                "service": "Design critique",
                "title": "Group design critique",
                "description": "Small-group critique of each participant's project.",
                "days_ahead": 9,
                "local_time": time(17),
                "duration_minutes": 120,
                "capacity": 6,
                "price_cents": 2500,
                "format": "in_person",
                "in_person_area": "Malasaña, Madrid",
                "meeting_place": "Demo venue (fictional), Calle Ejemplo 1",
            },
        ],
    },
    "demo.mentor.data@example.com": {
        "packages": [
            {
                "service": "Data science interview practice",
                "session_count": 4,
                "discount_percent": 10,
                "validity_days": 45,
            },
        ],
    },
    "demo.mentor.consulting@example.com": {
        "services": [
            {
                "title": "Case practice meetup",
                "description": "A full case interview, face to face.",
                "duration_minutes": 90,
                "price_cents": 10000,
                "online": False,
                "in_person": True,
                "in_person_area": "Mitte, Berlin",
            },
        ],
    },
}


class Command(BaseCommand):
    help = (
        "Create fictional demo accounts (admin, students, mentors) for showing the app locally. "
        "Development only; additive and idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            help="Password for every demo account (or set DEMO_PASSWORD). Default: random, printed once.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo only runs with DEBUG on (local development). Never seed production."
            )

        password = options["password"] or os.environ.get("DEMO_PASSWORD") or secrets.token_urlsafe(9)
        password_validation.validate_password(password)

        with transaction.atomic():
            admin, created = self._user(ADMIN, Role.ADMIN, password)
            rows = [("Admin", admin.email, "created" if created else "already existed")]
            for spec in STUDENTS:
                user, created = self._student(spec, password)
                rows.append(("Student", user.email, "created" if created else "already existed"))
            for spec in MENTORS:
                user, status = self._mentor(spec, password, admin)
                rows.append(("Mentor", user.email, status))

        for role, email, status in rows:
            self.stdout.write(f"  {role:<8} {email:<38} {status}")
        if any("existed" not in status for _, _, status in rows):
            source = (
                "the one you supplied"
                if (options["password"] or os.environ.get("DEMO_PASSWORD"))
                else password
            )
            self.stdout.write(f"\nPassword for newly created demo accounts: {source}")
        self.stdout.write("Existing accounts and records were left unchanged.")

    def _user(self, spec, role, password):
        existing = User.objects.filter(email__iexact=spec["email"]).first()
        if existing:
            return existing, False
        fields = {"first_name": spec["first_name"], "last_name": spec["last_name"]}
        if role == Role.ADMIN:
            user = User.objects.create_superuser(email=spec["email"], password=password, **fields)
        else:
            user = User.objects.create_user(
                email=spec["email"],
                password=password,
                role=role,
                timezone=spec.get("timezone", "UTC"),
                **fields,
            )
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at", "updated_at"])
        return user, True

    def _student(self, spec, password):
        user, created = self._user(spec, Role.STUDENT, password)
        if created:
            profile = StudentProfile.objects.create(
                user=user, headline=spec["headline"], country=spec["country"], bio=DEMO_NOTE
            )
            profile.interests.set(Category.objects.filter(name__in=spec["interests"]))
        return user, created

    def _mentor(self, spec, password, admin):
        user, created = self._user(spec, Role.MENTOR, password)
        if not created:
            mentor = MentorProfile.objects.filter(user=user).first()
            added = self._offerings(mentor, spec["email"]) if user.role == Role.MENTOR and mentor else 0
            return user, f"already existed (+{added} offerings)" if added else "already existed"
        mentor = mentor_services.create_mentor_profile(user)
        mentor_services.update_profile(
            mentor,
            {
                "headline": spec["headline"],
                "bio": f"{DEMO_NOTE}\n\n{spec['headline']}. {spec['years']} years of experience as a "
                f"{spec['profession'].lower()}.",
                "current_title": spec["title"],
                "profession": Profession.objects.get(slug=slugify(spec["profession"])),
                "years_experience": spec["years"],
                "country": spec["country"],
                "timezone": spec["timezone"],
                "meeting_url": f"https://meet.example.com/{mentor.slug}",
                "auto_accept": spec.get("auto_accept", False),
                "categories": list(Category.objects.filter(name__in=spec["categories"])),
                "skills": list(Skill.objects.filter(name__in=spec["skills"])),
                "languages": list(Language.objects.filter(code__in=spec["languages"])),
            },
            actor=user,
        )
        for title, description, minutes, cents in spec["services"]:
            mentor_services.create_service(
                mentor,
                {
                    "title": title,
                    "description": description,
                    "duration_minutes": minutes,
                    "price_cents": cents,
                },
            )
        self._offerings(mentor, spec["email"])
        mentor_services.replace_availability_rules(
            mentor, [{"weekday": d, "start_time": s, "end_time": e} for d, s, e in spec["hours"]]
        )
        verification = mentor_services.submit_for_verification(
            MentorProfile.objects.get(pk=mentor.pk),
            evidence_note="Created by seed_demo (demo data).",
            actor=user,
        )
        if not spec.get("approve", True):
            return user, "created (pending verification)"
        mentor_services.approve_verification(verification, actor=admin)
        return user, "created (approved)"

    def _offerings(self, mentor, email) -> int:
        """Create the demo services and packages this mentor doesn't have yet. Returns how many."""
        added = 0
        offerings = OFFERINGS.get(email, {})
        for data in offerings.get("services", []):
            if not mentor.services.filter(title=data["title"]).exists():
                mentor_services.create_service(mentor, dict(data))
                added += 1
        for data in offerings.get("packages", []):
            service = mentor.services.filter(title=data["service"], is_active=True).first()
            if service and not service.packages.filter(session_count=data["session_count"]).exists():
                fields = {k: v for k, v in data.items() if k != "service"}
                package_services.create_package(mentor, {**fields, "service_id": service.pk})
                added += 1
        now = timezone.now()
        for data in offerings.get("seminars", []):
            service = mentor.services.filter(title=data["service"], is_active=True).first()
            upcoming = mentor.seminars.filter(
                title=data["title"], status=SeminarStatus.SCHEDULED, start_at__gt=now
            )
            if service is None or upcoming.exists():
                continue
            day = (now + timedelta(days=data["days_ahead"])).astimezone(ZoneInfo(mentor.timezone)).date()
            start = datetime.combine(day, data["local_time"], tzinfo=ZoneInfo(mentor.timezone))
            fields = {k: v for k, v in data.items() if k not in ("service", "days_ahead", "local_time")}
            try:
                with transaction.atomic():
                    seminar_services.create_seminar(
                        mentor, {**fields, "service_id": service.pk, "start_at": start}
                    )
            except Conflict:
                continue  # the mentor has a session then; skip rather than move anything
            added += 1
        return added
