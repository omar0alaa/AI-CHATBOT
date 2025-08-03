# API Testing Guide

This guide explains how to test all routes in the AIChatBot-Python Flask app using Postman or similar tools. Each endpoint is described with method, URL, headers, and example payloads.

---

## Table of Contents
- [Chat Endpoint](#chat-endpoint)
- [Admin Knowledge Base Endpoints](#admin-knowledge-base-endpoints)
  - [Get All Q&A](#get-all-qa)
  - [Add Q&A](#add-qa)
  - [Edit Q&A](#edit-qa)
  - [Delete Q&A](#delete-qa)
- [Web Pages](#web-pages)

---

## Chat Endpoint

### POST `<ServerIP>/api/chat`
- **Description:** Send a user message to the chatbot and receive an answer.
- **Headers:** `Content-Type: application/json`
- **Body Example (English):**
```json
{
  "message": "What is your refund policy?",
  "lang": "en"
}
```
- **Body Example (Arabic):**
```json
{
  "message": "ما هي سياسة الاسترجاع؟",
  "lang": "ar"
}
```
- **Response:**
```json
{
  "message": "...chatbot answer..."
}
```

---

## Admin Knowledge Base Endpoints

### GET `<ServerIP>/admin/api/bank`
- **Description:** Retrieve all Q&A entries from the knowledge base.
- **Response:**
```json
[
  { "ID": 1, "question": "...", "answer": "..." },
  ...
]
```

### POST `<ServerIP>/admin/api/bank`
- **Description:** Add a new Q&A entry.
- **Headers:** `Content-Type: application/json`
- **Body Example:**
```json
{
  "question": "How do I reset my password?",
  "answer": "Click 'Forgot Password' on the login page."
}
```
- **Response:**
```json
{ "success": true }
```

### PUT `<ServerIP>/admin/api/bank/edit/<id>`
- **Description:** Edit an existing Q&A entry.
- **Headers:** `Content-Type: application/json`
- **URL Example:** `/admin/api/bank/edit/1`
- **Body Example:**
```json
{
  "question": "How do I reset my password?",
  "answer": "Use the 'Forgot Password' link."
}
```
- **Response:**
```json
{ "success": true }
```

### DELETE `<ServerIP>/admin/api/bank/delete/<id>`
- **Description:** Delete a Q&A entry.
- **URL Example:** `/admin/api/bank/delete/1`
- **Response:**
```json
{ "success": true }
```

---

## Web Pages

### GET `<ServerIP>/`
- **Description:** Main chat UI (HTML page).

### GET `<ServerIP>/admin/db`
- **Description:** Admin knowledge base editor (HTML page).
---

## Notes
- Ensure the Flask server is running locally or on server (default: `http://localhost:5000`).
- All API endpoints accept and return JSON.
- For admin endpoints, use the correct HTTP method (GET, POST, PUT, DELETE).
- For testing, you can use Postman, curl, or any HTTP client.

---

For more details, see the main README or source code.
