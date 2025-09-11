import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.models.schemas import ContactInfo, ContactResponse

logger = logging.getLogger(__name__)


@dataclass
class OnCallSchedule:
    """On-call schedule data structure."""

    specialty: str
    doctor_name: str
    phone: str
    pager: str
    start_time: datetime
    end_time: datetime
    backup_contact: Optional[Dict[str, str]] = None


class ContactService:
    """Mock service for Amion integration - on-call physician lookup."""

    def __init__(self):
        self.mock_schedules = self._initialize_mock_schedules()

    async def get_on_call(self, specialty: str) -> ContactResponse:
        """Get current on-call contact for specialty."""
        try:
            current_time = datetime.utcnow()

            # Find current on-call physician for specialty
            schedule = self._find_current_schedule(specialty.lower(), current_time)

            if not schedule:
                # Return default contact if no specific schedule found
                contacts = [
                    ContactInfo(
                        name="ED Attending",
                        role=f"{specialty.title()} Coverage",
                        phone="555-000-0000",
                        pager="555-000-0001",
                        coverage="on-call",
                        department=specialty.title(),
                    )
                ]
            else:
                contacts = [
                    ContactInfo(
                        name=schedule.doctor_name,
                        role=f"{specialty.title()} Attending",
                        phone=schedule.phone,
                        pager=schedule.pager,
                        coverage="on-call",
                        department=specialty.title(),
                    )
                ]

                # Add backup contact if available
                if schedule.backup_contact:
                    contacts.append(
                        ContactInfo(
                            name=schedule.backup_contact["name"],
                            role=f"{specialty.title()} Backup",
                            phone=schedule.backup_contact["phone"],
                            pager=schedule.backup_contact.get("pager", ""),
                            coverage="backup",
                            department=specialty.title(),
                        )
                    )

            return ContactResponse(
                specialty=specialty,
                contacts=contacts,
                updated_at=current_time,
                source="amion",
            )

        except Exception as e:
            logger.error(f"Contact lookup failed for {specialty}: {e}")
            raise

    async def get_schedule(
        self, specialty: str, days_ahead: int = 7
    ) -> List[OnCallSchedule]:
        """Get upcoming schedule for specialty."""
        current_time = datetime.utcnow()
        end_time = current_time + timedelta(days=days_ahead)

        schedules = []
        for schedule in self.mock_schedules:
            if (
                schedule.specialty.lower() == specialty.lower()
                and schedule.start_time <= end_time
                and schedule.end_time >= current_time
            ):
                schedules.append(schedule)

        return sorted(schedules, key=lambda x: x.start_time)

    async def validate_contact(self, phone: str = None, pager: str = None) -> bool:
        """Validate contact information format."""
        if phone and not self._is_valid_phone(phone):
            return False
        if pager and not self._is_valid_pager(pager):
            return False
        return True

    def _find_current_schedule(
        self, specialty: str, current_time: datetime
    ) -> Optional[OnCallSchedule]:
        """Find current on-call schedule for specialty."""
        for schedule in self.mock_schedules:
            if (
                schedule.specialty.lower() == specialty
                and schedule.start_time <= current_time <= schedule.end_time
            ):
                return schedule
        return None

    def _initialize_mock_schedules(self) -> List[OnCallSchedule]:
        """Initialize mock on-call schedules."""
        base_time = datetime.utcnow().replace(hour=8, minute=0, second=0, microsecond=0)

        schedules = []

        # Cardiology schedule
        schedules.append(
            OnCallSchedule(
                specialty="cardiology",
                doctor_name="Dr. Sarah Johnson",
                phone="555-123-4567",
                pager="555-987-6543",
                start_time=base_time,
                end_time=base_time + timedelta(hours=24),
                backup_contact={
                    "name": "Dr. Michael Torres",
                    "phone": "555-234-5678",
                    "pager": "555-876-5432",
                },
            )
        )

        # Surgery schedule
        schedules.append(
            OnCallSchedule(
                specialty="surgery",
                doctor_name="Dr. Michael Chen",
                phone="555-234-5678",
                pager="555-876-5432",
                start_time=base_time,
                end_time=base_time + timedelta(hours=12),
            )
        )

        # Neurology schedule
        schedules.append(
            OnCallSchedule(
                specialty="neurology",
                doctor_name="Dr. Emily Rodriguez",
                phone="555-345-6789",
                pager="555-765-4321",
                start_time=base_time,
                end_time=base_time + timedelta(hours=24),
            )
        )

        # Orthopedics schedule
        schedules.append(
            OnCallSchedule(
                specialty="orthopedics",
                doctor_name="Dr. David Kim",
                phone="555-456-7890",
                pager="555-654-3210",
                start_time=base_time,
                end_time=base_time + timedelta(hours=24),
            )
        )

        # Radiology schedule (24/7)
        schedules.append(
            OnCallSchedule(
                specialty="radiology",
                doctor_name="Dr. Lisa Wang",
                phone="555-567-8901",
                pager="555-543-2109",
                start_time=base_time,
                end_time=base_time + timedelta(days=7),
            )
        )

        # Emergency Medicine schedule
        schedules.append(
            OnCallSchedule(
                specialty="emergency",
                doctor_name="Dr. James Miller",
                phone="555-678-9012",
                pager="555-432-1098",
                start_time=base_time,
                end_time=base_time + timedelta(hours=12),
                backup_contact={
                    "name": "Dr. Rachel Park",
                    "phone": "555-789-0123",
                    "pager": "555-321-0987",
                },
            )
        )

        # Internal Medicine schedule
        schedules.append(
            OnCallSchedule(
                specialty="internal medicine",
                doctor_name="Dr. Robert Brown",
                phone="555-890-1234",
                pager="555-210-9876",
                start_time=base_time,
                end_time=base_time + timedelta(hours=24),
            )
        )

        # Pathology schedule
        schedules.append(
            OnCallSchedule(
                specialty="pathology",
                doctor_name="Dr. Jennifer Lee",
                phone="555-901-2345",
                pager="555-109-8765",
                start_time=base_time,
                end_time=base_time + timedelta(days=2),
            )
        )

        return schedules

    def _is_valid_phone(self, phone: str) -> bool:
        """Validate phone number format (xxx-xxx-xxxx)."""
        import re

        pattern = r"^\d{3}-\d{3}-\d{4}$"
        return bool(re.match(pattern, phone))

    def _is_valid_pager(self, pager: str) -> bool:
        """Validate pager number format."""
        import re

        pattern = r"^\d{3}-\d{3}-\d{4}$"
        return bool(re.match(pattern, pager))

    async def refresh_schedules(self) -> bool:
        """Mock method to refresh schedules from Amion (would make API call in production)."""
        try:
            logger.info("Refreshing on-call schedules from Amion")
            # In production, this would fetch from Amion API
            self.mock_schedules = self._initialize_mock_schedules()
            return True
        except Exception as e:
            logger.error(f"Failed to refresh schedules: {e}")
            return False

    def get_specialties(self) -> List[str]:
        """Get list of available specialties."""
        return list(set(schedule.specialty for schedule in self.mock_schedules))
