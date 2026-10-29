# Deployment checklist

1. Push the project to a public GitHub repository with a random/anonymous repository name.
2. Deploy `backend/` as a Docker web service on Render.
3. Set backend `FRONTEND_ORIGINS` to the exact Vercel app URL.
4. Deploy `frontend/` on Vercel with `VITE_API_BASE_URL` pointing to the backend.
5. Open `/api/health`, then open the frontend in an incognito window.
6. Select January 2026 and both forecast views. Confirm data coverage, timestamps, and metrics.
7. Record a 4–5 minute customer demo and 4–5 minute technical walkthrough; total video must be no longer than 10 minutes.
8. Make the video Unlisted and submit all links using the form in the challenge brief.
