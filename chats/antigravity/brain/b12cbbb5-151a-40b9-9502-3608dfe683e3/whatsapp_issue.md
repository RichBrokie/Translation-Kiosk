# WhatsApp Evolution API Disconnected

I've checked your CasaOS server and investigated why your Make.com workflows using the Evolution API are failing. 

### Cause of the Error
The Evolution API instance `myserver` was disconnected from WhatsApp. The server returned a `401 Unauthorized` error with the specific tag `device_removed`. This typically happens if:
1. The linked device was removed manually from the WhatsApp app on your phone.
2. WhatsApp invalidated the session (e.g. after a long period of inactivity, scanning a new code somewhere else, or an app update).

Because the API is disconnected, any requests coming from Make.com fail.

### How to Fix
You need to re-link your WhatsApp account to the Evolution API. Open WhatsApp on your phone, go to **Linked Devices**, select **Link a Device**, and scan the QR code below:

![WhatsApp QR Code](/home/ahmad/.gemini/antigravity/brain/b12cbbb5-151a-40b9-9502-3608dfe683e3/qr_code.png)

> [!NOTE]
> QR codes expire after a short amount of time (usually 20-40 seconds). If you receive an error scanning this code, let me know and I will generate a fresh one for you instantly!

Once scanned and connected, your Make.com workflows will automatically start working again.
