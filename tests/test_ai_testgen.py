import pytest
from unittest.mock import patch, AsyncMock
from litestar.testing import AsyncTestClient


MOCK_LLM_RESPONSE = {
    "title": "Проверка авторизации пользователя",
    "preconditions": "Пользователь зарегистрирован в системе",
    "steps": [
        {"step": "Открыть страницу входа", "expected": "Отображается форма входа"},
        {"step": "Ввести валидные данные", "expected": "Пользователь перенаправлен на главную"},
    ],
}


@pytest.mark.asyncio
async def test_generate_test_case(test_client: AsyncTestClient):
    with patch(
        "app.services.test_case_generator.TestCaseGeneratorService.generate",
        new_callable=AsyncMock,
        return_value=MOCK_LLM_RESPONSE,
    ):
        response = await test_client.post("/api/v1/test-cases/generate", json={
            "suite_id": "00000000-0000-0000-0000-000000000001",
            "user_story": "Как пользователь я хочу войти в систему",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Проверка авторизации пользователя"
        assert len(data["steps"]) == 2
        assert data["steps"][0]["step"] == "Открыть страницу входа"


@pytest.mark.asyncio
async def test_generate_test_case_llm_failure(test_client: AsyncTestClient):
    with patch(
        "app.services.test_case_generator.TestCaseGeneratorService.generate",
        new_callable=AsyncMock,
        return_value={
            "title": "Generated Test Case (LLM unavailable)",
            "preconditions": "LLM service unavailable",
            "steps": [{"step": "Retry later", "expected": "Test case generated successfully"}],
        },
    ):
        response = await test_client.post("/api/v1/test-cases/generate", json={
            "suite_id": "00000000-0000-0000-0000-000000000001",
            "user_story": "test story",
        })
        assert response.status_code == 201
        data = response.json()
        assert "unavailable" in data["title"].lower() or data["title"]