```markdown
# Twitch OAuth Token Retrieval Guide

This guide will help you obtain your Twitch API tokens: the **Authorization Code**, **Access Token**, and **Refresh Token** with the required scopes.

## Required Scopes

Your application will need the following scopes:
- `user:read:email`
- `user:read:broadcast`
- `channel:read:subscriptions`
- `chat:read`
- `chat:edit`

## 1. Create a Twitch Application

1. Visit the [Twitch Developer Console](https://dev.twitch.tv/console/apps) and sign in.
2. Click on **"Register Your Application"**.
3. Fill in the required details:
   - **Name:** Choose a name for your application.
   - **OAuth Redirect URLs:** Enter your redirect URL (e.g., `http://localhost`).
   - **Category:** Select the appropriate category.
4. Click **"Create"**.
5. Note your **Client ID** and **Client Secret** from your application settings.

## 2. Get an Authorization Code

Open your browser and visit the following URL (replace the placeholders with your actual details):

```
                                                                   XXXXXXXXXXXXXX
https://id.twitch.tv/oauth2/authorize?response_type=code&client_id=`CLIENT_ID`&redirect_uri=http://localhost&scope=user:read:email+user:read:broadcast+channel:read:subscriptions+chat:read+chat:edit+user_subscriptions&force_verify=true

https://id.twitch.tv/oauth2/authorize
    ?client_id=CLIENT_ID
    &redirect_uri=http://localhost
    &response_type=token
    &scope=chat:read+chat:edit+channel:read:subscriptions+user:read:broadcast+user:read:email+user_subscriptions
```

- **Replace:**
  - `YOUR_CLIENT_ID` with your actual Client ID.
  - `YOUR_REDIRECT_URI` with your actual redirect URL (URL-encoded if necessary).

After logging in and authorizing the application, you will be redirected to your specified redirect URL with a query parameter named `code`. This value is your **Authorization Code**.

## 3. Exchange the Authorization Code for Tokens

Use the following `curl` command (or an equivalent HTTP POST request) to exchange your Authorization Code for an Access Token and a Refresh Token:

```bash
curl -X POST "https://id.twitch.tv/oauth2/token" \
  -d "client_id=CLIENT_ID" \
  -d "client_secret=CLIENT_SECRET" \
  -d "code=ACCESS_TOKEN" \
  -d "grant_type=AUTHORIZATION_CODE" \
  -d "redirect_uri=http://localhost"

```

- **Replace:**
  - `YOUR_CLIENT_ID` with your Client ID.
  - `YOUR_CLIENT_SECRET` with your Client Secret.
  - `YOUR_AUTHORIZATION_CODE` with the code you obtained in Step 2.
  - `YOUR_REDIRECT_URI` with your redirect URL.

The response will be a JSON object that includes:
- **access_token**: Your new Access Token.
- **refresh_token**: Your new Refresh Token.
- Other details such as token expiry and granted scopes.

## 4. Refreshing Your Tokens

When your Access Token expires, you can refresh it using your Refresh Token. Use this `curl` command:

```bash
curl -X POST "https://id.twitch.tv/oauth2/token" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=YOUR_REFRESH_TOKEN" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

- **Replace:**
  - `YOUR_REFRESH_TOKEN` with your refresh token.
  - `YOUR_CLIENT_ID` and `YOUR_CLIENT_SECRET` with your application’s credentials.

The response will provide a new Access Token (and possibly a new Refresh Token).

## 5. Validation:

                                                                             ACCESS TOKEN
curl -X GET "https://id.twitch.tv/oauth2/validate" -H "Authorization: Bearer ACCESS_TOKEN"