# Weylus on X11: Full Setup!

Shifting to X11 is the perfect choice for this! It removes all of Wayland's security restrictions and allows software to easily create virtual monitors while maintaining full **Apple Pencil** pressure and tilt support.

I have set up two brand new shortcuts in your App Launcher to make extending your screen completely effortless.

> [!WARNING]
> **RESTART REQUIRED!**
> Because I added your user account to the new `uinput` group earlier to enable Apple Pencil pressure, you **must** reboot your computer for the system permissions to take effect. If you skip this, your Apple Pencil won't work correctly!

## How to Switch to X11
1. Save your work and **Log Out**.
2. Click your username on the login screen.
3. Click the **Gear icon** (⚙️) in the bottom right corner.
4. Select **"Zorin Desktop on Xorg"**.
5. Type your password and log in.

## How to Extend to your iPad
1. Connect your iPad to your laptop using a USB cable.
2. Open your App Launcher and search for **Start iPad Extended Screen**. Click it. *(This will instantly create a 1920x1080 virtual monitor off to the right of your main screen).*
3. Open your App Launcher and search for **Weylus**. Click it and hit the **Start** button.
   - *Ensure you select the new virtual monitor from the "Screen" dropdown.*
   - *Ensure "Enable Uinput" is checked for Apple Pencil pressure!*
4. On your iPad, open **Safari** (it must be Safari) and navigate to `http://localhost:1701`.

## How to Stop
When you are done using your iPad as a monitor:
1. Close the Safari tab on your iPad.
2. Close the Weylus app on your laptop.
3. Open your App Launcher and search for **Stop iPad Extended Screen**. Click it. *(This will instantly delete the virtual monitor and return your layout to normal).*
