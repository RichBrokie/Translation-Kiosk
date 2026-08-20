# Native Wayland Setup (No Apple Pencil Pressure)

If you **only** need basic touch support and an extended screen, and you **do not** care about Apple Pencil pressure or tilt, you can bypass Weylus completely! 

You can use GNOME's **built-in Remote Desktop** feature. The best part? It *natively* supports Wayland and dynamically creates a perfect extended virtual monitor as soon as you connect, and destroys it when you disconnect.

I have already configured your system to use "Extend" mode. Here is how to set up the rest over USB:

### Step 1: Enable USB Network
Because standard apps on your iPad cannot automatically "see" your PC over a raw USB cable, we need to create a local network over the USB cable.
1. Connect your iPad to your laptop via USB.
2. On your iPad, go to **Settings > Personal Hotspot** and turn it **ON**.
3. *If prompted, select "USB Only".*
4. Your Linux laptop will now automatically connect to the iPad's network and receive an IP Address (usually something like `172.20.10.x`).

### Step 2: Enable GNOME Remote Desktop
1. On your Linux laptop, open the **Settings** app.
2. Navigate to **Sharing > Remote Desktop**.
3. Turn **Remote Desktop** ON.
4. Under the "Login Details" section, set a simple **Username** and **Password**.

### Step 3: Find your USB IP Address
1. Open a terminal on your laptop and run: `ip a`
2. Look for an interface that resembles USB (often named `enp0s20...` or `usb0`) and note the `inet` IP address. *(Usually `172.20.10.x` or similar)*

### Step 4: Connect from iPad
1. On your iPad, download the free **Microsoft Remote Desktop** app from the App Store.
2. Open the app, tap the **+** button, and select **Add PC**.
3. In the **PC Name** field, type the IP address you found in Step 3.
4. Tap **Save**.
5. Tap the new PC icon to connect. Enter the Username and Password you created in Step 2.

**That's it!** As soon as you connect, Wayland will dynamically spawn a perfect extended second monitor, and you can drag windows over to your iPad. Touch works perfectly as a mouse, and when you disconnect the app, the second monitor disappears instantly.
