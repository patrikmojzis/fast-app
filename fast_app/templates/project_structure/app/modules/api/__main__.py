from fast_app.app_provider import boot
boot()

from app.modules.api.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)