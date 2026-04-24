# Steel Weight App - Split Deployment

This project is split into frontend and backend for deployment on Netlify and Render.

## Structure

- `frontend/` - Static HTML, CSS, JS files served by Netlify
- `backend/` - FastAPI backend deployed on Render

## Frontend Deployment (Netlify)

1. Push the `frontend/` folder to a GitHub repository.
2. Connect the repo to Netlify.
3. Set build command to none (static site).
4. Publish directory: `.`
5. Update `_redirects` with your Render backend URL:
   ```
   /api/* https://your-render-app.render.com/api/:splat 200
   ```

## Backend Deployment (Render)

1. Push the `backend/` folder to a GitHub repository.
2. Connect to Render, select Python, set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Set environment variables:
   - `DATABASE_URL` - PostgreSQL connection string
   - `SESSION_SECRET` - Random secret for sessions

## Local Development

For local dev, you can run the backend and serve frontend separately.

Backend: `uvicorn app.main:app --reload`

Frontend: Use a local server or open HTML files directly (but API calls won't work due to CORS).

For full local, modify CORS in main.py to allow localhost origins.