import pytest
from core.views import create_parent_account

@pytest.mark.django_db
class TestCreateParentAccount:

    def test_create_parent_success(self):
        parent = create_parent_account(
            username="parent1",
            email="parent@test.com",
            password="securepass123",
            phone_number="1234567890",
            address="123 Main Street",
        )

        assert parent.id is not None
        assert parent.phone_number == "1234567890"
        assert parent.address == "123 Main Street"

        user = parent.user
        assert user.username == "parent1"
        assert user.email == "parent@test.com"
        assert user.check_password("securepass123")

    def test_duplicate_email_raises_value_error(self):
        create_parent_account(
            username="parent1",
            email="duplicate@test.com",
            password="pass123",
            phone_number="111",
            address="addr",
        )

        with pytest.raises(ValueError, match="Email already in use"):
            create_parent_account(
                username="parent2",
                email="duplicate@test.com",
                password="pass123",
                phone_number="222",
                address="addr",
            )
