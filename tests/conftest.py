import pytest

from app.db.database import init_db
from app.llm.mock_client import MockLLMClient
from app.services.recipe_service import RecipeService


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
    return RecipeService(mock_llm, db_path)
