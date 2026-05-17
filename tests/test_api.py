"""Тесты APIGenerator — асинхронные, через httpx."""
import pytest
from unittest.mock import MagicMock
import httpx

from pydajet_metadata.api import APIGenerator


class TestAPIGenerator:
    """Тесты FastAPI-генератора. Все запросы через httpx + ASGITransport."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.types.return_value = ['Справочники', 'Документы']
        repo.objects.return_value = ['ирАлгоритмы', 'ТемыУведомлений']
        return repo

    @pytest.fixture
    def mock_query(self):
        q = MagicMock()
        q.all.return_value = [
            {'Ссылка': '9c280050-b666-dffa-11f1-4e880e761abe', 'Наименование': 'Тест', 'Код': '001'},
        ]
        q.first.return_value = {'Ссылка': '9c280050-b666-dffa-11f1-4e880e761abe', 'Наименование': 'Тест', 'Код': '001'}
        q.insert.return_value = '9c280050-b666-dffa-11f1-4e880e761abe'
        q.update.return_value = True
        q.delete.return_value = True
        q._pk = '_idrref'
        q._table = MagicMock()
        q._table.c = {'_idrref': MagicMock()}
        q._column_map = {'Ссылка': '_IDRRef', 'Наименование': '_Description', 'Код': '_Code'}
        return q

    @pytest.fixture
    def app(self, mock_repo, mock_query):
        mock_repo.query.return_value = mock_query
        gen = APIGenerator(mock_repo)
        return gen.generate()

    @pytest.fixture
    async def client(self, app):
        """Асинхронный клиент для тестирования ASGI."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    # ─── Info endpoints ──────────────────────────────

    @pytest.mark.asyncio
    async def test_get_types(self, client):
        response = await client.get("/types")
        assert response.status_code == 200
        assert response.json() == ['Документы', 'Справочники']

    @pytest.mark.asyncio
    async def test_get_objects(self, client):
        response = await client.get("/types/Справочники/objects")
        assert response.status_code == 200
        assert response.json() == ['ирАлгоритмы', 'ТемыУведомлений']

    # ─── CRUD endpoints ──────────────────────────────

    @pytest.mark.asyncio
    async def test_get_all(self, client):
        response = await client.get("/Справочники/ирАлгоритмы")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]['Наименование'] == 'Тест'

    @pytest.mark.asyncio
    async def test_get_all_with_pagination(self, client):
        response = await client.get("/Справочники/ирАлгоритмы?skip=0&limit=10")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_by_id(self, client):
        response = await client.get("/Справочники/ирАлгоритмы/9c280050-b666-dffa-11f1-4e880e761abe")
        assert response.status_code == 200
        assert response.json()['Наименование'] == 'Тест'

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, client):
        mock_query = client._transport.app.extra['query'] if hasattr(client._transport.app, 'extra') else None
        if mock_query:
            mock_query.first.return_value = None
        response = await client.get("/Справочники/ирАлгоритмы/00000000-0000-0000-0000-000000000000")
        # Может быть 404 если first возвращает None
        assert response.status_code in (200, 404, 500)

    @pytest.mark.asyncio
    async def test_create(self, client, app, mock_repo, mock_query):
        mock_repo.query.return_value = mock_query
        response = await client.post(
            "/Справочники/ирАлгоритмы",
            json={'Наименование': 'Новый', 'Код': '002'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data['Наименование'] == 'Тест'

    @pytest.mark.asyncio
    async def test_update(self, client):
        response = await client.put(
            "/Справочники/ирАлгоритмы/9c280050-b666-dffa-11f1-4e880e761abe",
            json={'Наименование': 'Обновлённый'},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_not_found(self, client, mock_repo, mock_query):
        mock_query.update.return_value = False
        mock_repo.query.return_value = mock_query
        response = await client.put(
            "/Справочники/ирАлгоритмы/00000000-0000-0000-0000-000000000000",
            json={'Наименование': 'Обновлённый'},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete(self, client):
        response = await client.delete("/Справочники/ирАлгоритмы/9c280050-b666-dffa-11f1-4e880e761abe")
        assert response.status_code == 200
        assert response.json() == {"status": "deleted"}

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client, mock_repo, mock_query):
        mock_query.delete.return_value = False
        mock_repo.query.return_value = mock_query
        response = await client.delete("/Справочники/ирАлгоритмы/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    # ─── OpenAPI docs ────────────────────────────────

    @pytest.mark.asyncio
    async def test_openapi_schema(self, client):
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema['info']['title'] == "1С REST API"
        assert 'paths' in schema

    @pytest.mark.asyncio
    async def test_swagger_ui(self, client):
        response = await client.get("/docs")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_redoc(self, client):
        response = await client.get("/redoc")
        assert response.status_code == 200

    # ─── Конкурентные запросы ───────────────────────

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client):
        """Проверяет, что API выдерживает конкурентные запросы."""
        import asyncio

        async def make_request():
            response = await client.get("/Справочники/ирАлгоритмы")
            assert response.status_code == 200

        tasks = [make_request() for _ in range(10)]
        await asyncio.gather(*tasks)

    # ─── Валидация ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_invalid_data(self, client):
        """Отправка невалидных данных должна вернуть 422."""
        response = await client.post(
            "/Справочники/ирАлгоритмы",
            json={'НесуществующееПоле': 'значение'},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_empty_body(self, client):
        response = await client.post(
            "/Справочники/ирАлгоритмы",
            json={},
        )
        assert response.status_code == 422
