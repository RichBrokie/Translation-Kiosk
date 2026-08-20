# Evolution API + Make.com — Complete Guide

## ✅ Current Status

| Component | Status | Details |
|---|---|---|
| **Disk** | 58% used (was 100%) | Freed ~3.5GB |
| **PostgreSQL** | ✅ Running | Recovered from disk-full crash |
| **Evolution API** | ✅ v2.3.7 running | Port 8081 → 8080 |
| **WhatsApp** | ✅ Connected | Ahmad's account (`994998250699`) |
| **Webhook** | ✅ Active | Pointing to Make.com |
| **Public URL** | `https://evolution.weplaymc.online` | Cloudflare tunnel |

### What Was Fixed
- **Root cause**: Disk was 100% full — PostgreSQL couldn't write WAL files, causing both DB and API to restart-loop
- **Cleaned**: ~800MB journal logs, 1.37GB deprecated `atendai/evolution-api` image, ~290MB unused Docker images
- **Result**: 3.2GB free space, all containers healthy

---

## 🔧 Your API Credentials

| Setting | Value |
|---|---|
| **API Base URL** | `https://evolution.weplaymc.online` |
| **API Key** | `Malhi542` |
| **Instance Name** | `myserver` |
| **Webhook URL** | `https://hook.eu1.make.com/c9jarh4n4a2xiejbvjy2q3twn824hl5e` |

---

## 📱 Everything You Can Do with Evolution API + Make.com

### 1. Send Text Messages
**Make.com Module**: HTTP → Make a Request

| Field | Value |
|---|---|
| URL | `https://evolution.weplaymc.online/message/sendText/myserver` |
| Method | POST |
| Header: `apikey` | `Malhi542` |
| Header: `Content-Type` | `application/json` |

```json
{
  "number": "923001234567",
  "text": "Hello from Make.com!"
}
```

### 2. Send Images/Media
**URL**: `POST /message/sendMedia/myserver`

```json
{
  "number": "923001234567",
  "media": {
    "mediatype": "image",
    "caption": "Check this out!",
    "media": "https://example.com/image.jpg"
  }
}
```

### 3. Send Documents/Files
**URL**: `POST /message/sendMedia/myserver`

```json
{
  "number": "923001234567",
  "media": {
    "mediatype": "document",
    "caption": "Here's your invoice",
    "media": "https://example.com/invoice.pdf",
    "fileName": "invoice.pdf"
  }
}
```

### 4. Send Audio Messages
**URL**: `POST /message/sendWhatsAppAudio/myserver`

```json
{
  "number": "923001234567",
  "audio": "https://example.com/audio.mp3"
}
```

### 5. Send Location
**URL**: `POST /message/sendLocation/myserver`

```json
{
  "number": "923001234567",
  "location": {
    "name": "My Business",
    "address": "123 Main St",
    "latitude": -23.561,
    "longitude": -46.656
  }
}
```

### 6. Send Contacts (vCard)
**URL**: `POST /message/sendContact/myserver`

```json
{
  "number": "923001234567",
  "contact": [
    {
      "fullName": "John Doe",
      "wuid": "14155551234@s.whatsapp.net",
      "phoneNumber": "+14155551234"
    }
  ]
}
```

### 7. Send Buttons / Interactive Lists
**URL**: `POST /message/sendButtons/myserver`

```json
{
  "number": "923001234567",
  "title": "Choose an option",
  "description": "What would you like to do?",
  "footer": "Powered by Evolution API",
  "buttons": [
    { "buttonText": { "displayText": "Option 1" }, "buttonId": "1" },
    { "buttonText": { "displayText": "Option 2" }, "buttonId": "2" }
  ]
}
```

### 8. Send Polls
**URL**: `POST /message/sendPoll/myserver`

```json
{
  "number": "923001234567",
  "name": "What do you prefer?",
  "values": ["Option A", "Option B", "Option C"],
  "selectableCount": 1
}
```

### 9. Send Stickers
**URL**: `POST /message/sendSticker/myserver`

```json
{
  "number": "923001234567",
  "sticker": "https://example.com/sticker.webp"
}
```

---

## 📥 Receiving Messages (Webhook → Make.com)

Your webhook is already configured. In Make.com:

1. Add a **Webhooks → Custom Webhook** module
2. Use URL: `https://hook.eu1.make.com/c9jarh4n4a2xiejbvjy2q3twn824hl5e`
3. Events you'll receive:
   - `MESSAGES_UPSERT` — New incoming messages
   - `MESSAGES_UPDATE` — Message status changes (sent, delivered, read)
   - `SEND_MESSAGE` — Outbound message confirmations
   - `CONTACTS_UPSERT` — New contacts
   - `CONNECTION_UPDATE` — Connection status changes

### Webhook Payload Example (incoming message):
```json
{
  "event": "messages.upsert",
  "instance": "myserver",
  "data": {
    "key": {
      "remoteJid": "923001234567@s.whatsapp.net",
      "fromMe": false,
      "id": "ABCDEF123"
    },
    "message": {
      "conversation": "Hello!"
    },
    "pushName": "Contact Name"
  }
}
```

---

## 🤖 Make.com Automation Ideas

### Auto-Reply Bot
```
Webhook (receive msg) → Router → Filter by keyword → HTTP (send reply)
```

### CRM Integration
```
Webhook (receive msg) → Google Sheets (log) → Filter → HTTP (auto-reply)
```

### Order Notifications
```
Shopify/WooCommerce trigger → HTTP (send WhatsApp confirmation)
```

### Appointment Reminders
```
Google Calendar trigger → HTTP (send WhatsApp reminder)
```

### Lead Capture
```
Webhook (receive msg) → HubSpot/Salesforce (create contact) → HTTP (send welcome)
```

### Support Ticket System
```
Webhook (receive msg) → Zendesk/Freshdesk (create ticket) → HTTP (send ticket #)
```

---

## 🔍 Other Useful API Endpoints

| Action | Method | Endpoint |
|---|---|---|
| Check connection status | GET | `/instance/fetchInstances` |
| Get QR code (if disconnected) | GET | `/instance/connect/myserver` |
| Logout WhatsApp | DELETE | `/instance/logout/myserver` |
| Get all contacts | GET | `/chat/findContacts/myserver` |
| Get all chats | GET | `/chat/findChats/myserver` |
| Get messages from chat | POST | `/chat/findMessages/myserver` |
| Set profile picture | PUT | `/instance/setProfilePicture/myserver` |
| Check if number is on WhatsApp | POST | `/chat/whatsappNumbers/myserver` |
| Get profile picture URL | GET | `/chat/getProfilePicture/myserver?number=923001234567` |
| Mark message as read | PUT | `/chat/markMessageAsRead/myserver` |
| Archive/unarchive chat | PUT | `/chat/archiveChat/myserver` |
| Block/unblock contact | PUT | `/chat/blockContact/myserver` |

> [!IMPORTANT]
> All API calls require the header `apikey: Malhi542`

---

## ⚠️ Maintenance Tips

1. **Monitor disk space** — The 7.8GB disk is small. Set up journal size limits:
   ```bash
   # Already cleaned to 50MB, but add permanent limit:
   echo "SystemMaxUse=50M" >> /etc/systemd/journald.conf
   systemctl restart systemd-journald
   ```

2. **Docker log rotation** — Add to container configs:
   ```yaml
   logging:
     driver: json-file
     options:
       max-size: "10m"
       max-file: "3"
   ```

3. **If WhatsApp disconnects** — Visit: `GET https://evolution.weplaymc.online/instance/connect/myserver` with your API key to get a new QR code
