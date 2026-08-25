Source: https://blink.ucsd.edu/technology/network/connections/off-campus/remote-desktop/remote-connection.html
Fetched: 2026-08-24T07:29:32.214Z · fidelity 97.1 (band A) · pipeline rubric/1.2.0

# Connecting to a University Issued Desktop From a Home Computer

Last Updated: October 25, 2024 3:36:10 PM PDT

Find out how to use a Remote Desktop application to access your campus computer.

Remote Desktop access has different setup instructions depending on your home and office computer systems. Below are variations to help you remotely access your campus computer.

**Note:** if your home computer is a PC, you must have Windows 7 or higher, up-to-date antivirus software, and automatic operating system updates enabled.

If you are unable to connect to a UC San Diego computer using Remote Desktop from your personal computer, check that you are first connected to the campus network through the campus VPN.

If you are still unable to connect, contact the [ITS Service Desk](mailto:servicedesk@ucsd.edu), (858) 246-4357.

## [Using a home Windows 7 /10 computer to access a campus PC computer](#)

Use the Remote Desktop Connection option from Windows to access your campus computer.

### Step 1: Prepare Windows 7 /10 computer for remote access

1.  Open the Settings app
2.  Click the **System** category
3.  Click the **Remote Desktop** page
4.  Toggle the “Enable Remote Desktop” button to the “On” position \*
    
    \*This might already be set for Remote Desktop and greyed out. If it’s set to off and greyed out, contact us, department policy may be set to disable RDP.
    
5.  Click on **Power & Sleep** and set Sleep to **never**
6.  Find the Windows 10 IP address (if you’re unsure of the IP, follow below instructions, otherwise skip step

To find the IP address on Windows 10, without using the command prompt:

1.  Click the **Start icon** and select **Settings** 
2.  Click the **Network & Internet** icon
3.  To view the IP address of a wired connection, select **Ethernet** on the left menu pane and select your network connection, your IP address will appear next to "IPv4 Address"

7.  Connect to the UC San Diego Cisco VPN

### Step 2: Connect remotely to campus computer

1.  Connect to the [campus VPN](https://blink.ucsd.edu/technology/network/connections/off-campus/VPN/index.html).
2.  Click the search bar on the Taskbar
3.  Type "remote desktop": A list of search results appears
4.  Click **Remote Desktop Connection**
5.  Click on **Show Options**
6.  Click on the **Experience** tab  
    From the drop-down menu, select **LAN (10 Mbps or higher)
    
    ![remote desktop connection page](https://blink.ucsd.edu/_images/technology-tab/network/remote-desktop-2.jpg)**
7.  Click **Connect**  
    Windows initiates the remote connection; then you will be asked to enter your AD credentials
8.  Enter the AD username and password that you use on the computer you’re connecting to; then click **OK**
9.  If you’re informed that the remote computer couldn’t be authenticated due to problems with its security certificate, click **Yes** to connect anyway
    
    ![remote desktop authentication pop up](https://blink.ucsd.edu/_images/technology-tab/network/remote-desktop.png)
    

You’re now connected to the UC San Diego remote computer and can use it as though it were your local computer

* * *

### Trouble shooting

If Remote Desktop Connection says that it can’t connect to the remote computer, check the following:

1.  Make sure you are connected to the campus network using the [campus VPN](https://blink.ucsd.edu/technology/network/connections/off-campus/VPN/index.html)
2.  That the remote computer is turned on (powered On)
3.  The remote computer is available on the network
4.  The remote computer's Windows setting Allow Remote Connections is enabled

[Submit a ServiceNow ticket](https://servicedesk.ucsd.edu/) if you are unable to connect to a UC San Diego remote computer using Remote Desktop from your personal computer.

### Close the connection

When you finish using the Remote Desktop Connection:

1.  Press **Ctrl Alt End** to view the lock, sign out, change password and task manager options on the remote Windows 10 computer
    
    ![remote sign out](https://blink.ucsd.edu/technology/_images/remote-sign-out.png)
    
2.  Close the Remote Desktop Connection app by clicking the **X** button on the top
3.  Click **OK**

The remote session is now disconnected.

## [Using a home Macintosh to access a campus Windows 10 computer](#)

Use the Remote Desktop Protocol (RDP) App from Mac OS to access a Windows 10 from your Mac computer:

### Step 1: Prepare Campus Windows 10 computer for remote access 

1.  Open the Settings app on the campus computer
2.  Click the **System** category
3.  Click the **Remote Desktop** page
4.  Toggle the “Enable Remote Desktop” button to the “On” position \*
    
    \* This might already be set for Remote Desktop and greyed out. If it’s set to off and greyed out, contact us, department policy may be set to disable RDP.
    
5.  Click on **Power & Sleep** and set Sleep to **never**
6.  Find the Windows 10 IP address (if you’re unsure of the IP, follow below instructions, otherwise skip steps a-c)

To find the IP address on Windows 10, without using the command prompt:

1.  Click the **Start icon** and select **Settings**
2.  Click the **Network & Internet** icon
3.  To view the IP address of a wired connection, select **Ethernet** on the left menu pane and select your network connection, your IP address will appear next to "IPv4 Address"

7.  You should now be able to connect from devices on your local network, using your PC’s IP address or hostname

### Step 2: Prepare Mac OS Computer to remotely access a Windows Computer 

1.  If you do not have Remote Desktop for Mac [download/install the Remote Desktop app from the Apple App Store](https://itunes.apple.com/app/microsoft-remote-desktop/id1295203466?mt=12)
2.  Connect to the [campus VPN](https://blink.ucsd.edu/technology/network/connections/off-campus/VPN/index.html).
    1.  If you do not have Cisco VPN app on your Mac computer, [download the app](https://support.ucsd.edu/services?id=kb_article_view&sysparm_article=KB0020109).
3.  Open and setup Remote Desktop app
4.  In the RDP upper menu, click **+**, and **Add PC**
5.  Enter the following information:
    1.  Enter IP address of the remote UC San Diego Windows
    2.  In the User Account add your UC San Diego login username (ie: AD\\username)
    3.  (Optional) Manage your saved user accounts in the preferences of the app
    4.  You can also set these optional settings for the connection:
        1.  Set a friendly name (ie: MY OFFICE PC)
        2.  Enable connect to Admin Mode
        3.  Redirect local folders into a remote session
        4.  Forward local printers
        5.  Forward Smart Cards
    5.  Click **Save**

### Step 3: Connect to remote computer 

1.  Double click Remote Desktop app to start
2.  Windows initiates the remote connection to the campus computer
    1.  If you created your User Account, it will auto-login
    2.  If not, it will ask for your username/password
    3.  If you are informed that the remote computer couldn’t be authenticated due to problems with its security certificate, click **Yes** to connect anyway
        
        ![remote desktop authentication pop up](https://blink.ucsd.edu/_images/technology-tab/network/remote-desktop.png)
        

You’re now connected to the UC San Diego remote computer and can use it as though it were your local computer.

* * *

### Trouble shooting

If Remote Desktop Connection says that it can’t connect to the remote computer, check the following:

1.  Make sure you are connected to the campus network using the [campus VPN](https://blink.ucsd.edu/technology/network/connections/off-campus/VPN/index.html) 
2.  That the remote computer is turned on (powered On)
3.  The remote computer is available on the network 
4.  The remote computer's setting to Allow Remote Connections is enabled

[Submit a ServiceNow ticket](https://servicedesk.ucsd.edu/) if you are unable to connect to a UC San Diego remote computer using Remote Desktop from your personal computer

### Customize your display resolution

You can specify the display resolution for the remote desktop session.

1.  In the Connection Center, click **Preferences**
2.  Click **Resolution**
3.  Click **+**
4.  Enter a resolution height and width, and then click **OK**
    1.  To delete the resolution, select it, and then click **-** key

Displays have separate spaces If you are running Mac OS X 10.9 and disabled displays have separate spaces in Mavericks (System Preferences > Mission Control), you need to configure this setting in the remote desktop client using the same option.

### Use a keyboard in a remote session

Mac keyboard layouts differ from the Windows keyboard layouts.

-   The Command key on the Mac keyboard equals the Windows key.
-   To perform actions that use the Command button on the Mac, you will need to use the control button in Windows (e.g.: Copy = Ctrl + C).
-   The function keys can be activated in the session by pressing additionally the FN key (e.g.: FN + F1).
-   The Alt key to the right of the space bar on the Mac keyboard equals the Alt Gr/right Alt key in Windows.

By default, the remote session will use the same keyboard locale as the OS you're running the client on. (If your Mac is running an en-us OS, that will be used for the remote sessions as well.) If the OS keyboard locale is not used, check the keyboard setting on the remote PC and change it manually.

### Close the connection

When you finish using the Remote Desktop Connection:

1.  Press **Ctrl** **Alt** **Del** to view the lock, sign out, change password and task manager options on the remote Windows 10 computer
    
    ![remote sign out](https://blink.ucsd.edu/technology/_images/remote-sign-out.png)
    
    Select **Sign out** to log off from the remote Windows 10 computer
    
2.  Close the Remote Desktop Connection app by clicking the **X** button on the top
3.  Click **OK**

For questions or assistance with connections, contact the [ITS Service Desk](https://support.ucsd.edu/its/), (858) 246-4357.

## Key facts

- Last Updated: October 25, 2024 3:36:10 PM PDT
- If you are still unable to connect, contact the [ITS Service Desk](mailto:servicedesk@ucsd.edu), (858) 246-4357.
- For questions or assistance with connections, contact the [ITS Service Desk](https://support.ucsd.edu/its/), (858) 246-4357.

## Who to contact

- If you are still unable to connect, contact the [ITS Service Desk](mailto:servicedesk@ucsd.edu), (858) 246-4357.
- For questions or assistance with connections, contact the [ITS Service Desk](https://support.ucsd.edu/its/), (858) 246-4357.
