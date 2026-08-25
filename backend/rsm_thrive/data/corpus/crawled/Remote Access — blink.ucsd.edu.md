Source: https://blink.ucsd.edu/technology/network/connections/off-campus/remote-desktop/index.html
Fetched: 2026-08-24T07:29:31.948Z · fidelity 80.2 (band B) · pipeline rubric/1.2.0

# Remote Access

Last Updated: June 28, 2023 11:15:10 AM PDT

Learn how to securely access university computers from remote locations

Accessing university computers from home, a conference, or from the field is something thousands of faculty, staff, and students do every day. To make this access work, the university computer is configured to accept connections from almost anywhere in the world. Hackers are increasingly taking advantage of these connections to spread ransomware. The following measures address the security of remote access software.

## Restrictions, Requirements, and Recommendations

-   All remote access protocols must be configured to use multi-factor authentication. Please check the documentation of your remote access product for details.
-   Telnet is not permitted under any circumstances
-   Remote Desktop Protocol (RDP), Apple Remote Desktop (ADP), and Virtual Network Computing (VNC) are restricted to VPN users. _You must connect to [the campus VPN](https://blink.ucsd.edu/technology/network/connections/off-campus/VPN/index.html) before starting any of these remote access clients._
-   It is recommended to restrict Secure Shell (SSH) to VPN users, ensuring multi-factor authentication (leveraged by the VPN).

## Remote Access Methods and Specifics

## Apple Remote Desktop (ADP)

ADP is a technology developed by Apple, based on VNC, that provides you with access to Apple computers from another computer. It presents you with the desktop of the remote computer allowing you to work as if you were physically sitting at the remote computer.

Using ADP to access computers at UC San Diego **requires** you to access the campus network by first connecting to the [campus VPN](https://blink.ucsd.edu/technology/network/connections/off-campus/VPN/index.html).

## Remote Access Protocol (RDP)

RDP is a technology that provides you with access to a Windows computer from another computer. It presents you with the desktop of the remote computer allowing you to work as though you were physically sitting at the remote computer.

Using RDP to access computers at UC San Diego **requires** you to access the campus network by first connecting to the [campus VPN](https://blink.ucsd.edu/technology/network/connections/off-campus/VPN/index.html). Within the UC System, 80% of ransomware attacks succeed by taking advantage of insecurely configured or maintained RDP accounts.

## Secure Shell or Secure Socket Shell (SSH)

SSH, also known as Secure Shell or Secure Socket Shell, is a network protocol that gives users, particularly system administrators, a secure way to access a computer over an unsecured network.

When using SSH to access computers at UC San Diego, it is recommended to access the campus network through the campus VPN.

-   SSH is the most widely used remote access protocol, and it is highly attacked.
-   On a typical day, more than 160,000 internet addresses maliciously attempt to connect to campus using SSH, which is more than 2 million attempts per week.

Configuring SSH for security generally depends on the version of SSH in use. Common guidance can be found at:

-   Linux [OpenSSH security and hardening](https://linux-audit.com/audit-and-harden-your-ssh-configuration/)
-   Microsoft [OpenSSH in Windows](https://docs.microsoft.com/en-us/windows-server/administration/openssh/openssh_overview)

## Telnet

Telnet is an application protocol used on the Internet or local area network to provide a bidirectional, interactive text-oriented communication facility using a virtual terminal connection.

_Telnet is intrinsically insecure and Telnet connections to the campus are forbidden and blocked from connecting to campus computers._

## Virtual Network Computing (VNC)

VNC is a graphical desktop-sharing system that uses the Remote Frame Buffer protocol (RFB) to remotely control another computer.

Using VNC to access computers at UC San Diego **requires** you to access the campus network by first connecting to the [campus VPN](https://blink.ucsd.edu/technology/network/connections/off-campus/VPN/index.html). VNC requires careful configuration to ensure that it is secure, and should be configured to require two-step authentication.

See the following for guidance:

-   [https://linuxtechlab.com/secure-vnc-server-tls-encryption/](https://linuxtechlab.com/secure-vnc-server-tls-encryption/)
-   https://www.howtoforge.com/secure\_vnc\_remote\_access\_with\_two\_factor\_authentication

## Virtual Private Network (VPN)

VPNs are a way to ensure that your network traffic is encrypted between your computer and any service you access. While running a VPN to access a University service you are protecting your data from being intercepted and read.

Some campus services require you to have the VPN running to access them. It is recommended that you _always_ use the VPN when working remotely.

Please see [our VPN pages](https://blink.ucsd.edu/technology/network/connections/off-campus/VPN/index.html) for more information.

## FAQ

## [What are these remote desktop protocols?](#)

ADP, RDP and VNC are a technology that provides you with access to macOS, Windows, and Linux computers from another computer. It presents you with the graphical desktop of the remote computer in a window on your local computer, allowing you to work as if you were physically sitting at the remote computer.

## [Why will we need to use the VPN to run remote desktops?](#)

Evidence within UC has shown that up to 80% of ransomware attacks begin by the hackers taking advantage of weak, unsecured or outdated remote desktop services.

Furthermore, while the campus VPN requires the use of two-step login, by default remote desktop clients do not. By requiring users to use the VPN prior to running a remote desktop, hackers from off campus will no longer be able to attack campus computers through remote desktop services.

## [I use remote desktops regularly, will VPN force me to reconfigure or change how I use it?](#)

No. You will simply need to start the [campus VPN](https://blink.ucsd.edu/technology/network/connections/off-campus/VPN/index.html) _before_ attempting to connect with ADP/RDP/VNC to any campus resource.

## Key facts

- Last Updated: June 28, 2023 11:15:10 AM PDT
- Within the UC System, 80% of ransomware attacks succeed by taking advantage of insecurely configured or maintained RDP accounts.
- Evidence within UC has shown that up to 80% of ransomware attacks begin by the hackers taking advantage of weak, unsecured or outdated remote desktop services.
