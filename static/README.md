# Browser Client

`index.html` is the single-page browser client served by `app.main` at `/`. It starts workflow runs through `POST /api/run`, then listens to `/api/events` over Server-Sent Events and renders planning, research, code, test, healing, and delivery updates.

There is no separate frontend build step. Edit the HTML and refresh the running FastAPI service.