import pytest

from cookwithai.db.database import GUEST_USER_ID, init_db
from cookwithai.llm.mock_client import MockLLMClient
from cookwithai.services.auth_service import AuthService
from cookwithai.services.recipe_service import RecipeService


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def mock_llm():
    return MockLLMClient(latency_seconds=0)


@pytest.fixture
def service(mock_llm, db_path):
    return RecipeService(mock_llm, db_path, GUEST_USER_ID)


@pytest.fixture
def guest_service(mock_llm, db_path):
    return RecipeService(mock_llm, db_path, None)


@pytest.fixture
def auth(db_path):
    return AuthService(db_path)
