"""Vercel entrypoint for the Flask app."""

from app import app

# Vercel Python runtime looks for `app` (WSGI callable)
