import pytest

import app as app_module


@pytest.fixture
def client(tmp_path):
    app_module.app.config["DB_PATH"] = str(tmp_path / "test.db")
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.mark.parametrize("path", ["/static/style.css", "/static/background.js"])
def test_static_assets_are_served(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("url", ["/", "/report", "/budgets"])
def test_every_page_has_the_background_canvas_and_script(client, url):
    html = client.get(url).data.decode()
    assert 'id="bg-canvas"' in html
    assert 'aria-hidden="true"' in html
    assert "background.js" in html
    assert "style.css" in html
