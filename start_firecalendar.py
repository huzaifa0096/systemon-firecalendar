"""Launch the local observatory and open the browser once its socket is listening."""
import webbrowser
import uvicorn


class DesktopServer(uvicorn.Server):
    async def startup(self, sockets=None):
        await super().startup(sockets=sockets)
        if self.started:
            webbrowser.open("http://127.0.0.1:8010/")


if __name__ == "__main__":
    DesktopServer(uvicorn.Config("app.main:app", host="127.0.0.1", port=8010)).run()
