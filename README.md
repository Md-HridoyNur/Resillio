# RESILIO
### Disaster Resource Coordination and Volunteer Management System

**Connecting communities, coordinating resources and supporting volunteers during disasters.**

RESILIO is a web application that brings help requests, resource offers, volunteer activities and shelter information into one platform. It helps affected people communicate their needs while enabling donors and relief organizations to organize supplies and track assistance through confirmed delivery.

## Key Features

- **Help Requests:** Post needs with item details, quantity, area and urgency.
- **Resource Offers:** Share available supplies and track remaining stock.
- **Resource Matching:** Find compatible offers based on item, unit, availability and area.
- **Volunteer Coordination:** Assign volunteers and track delivery progress.
- **Delivery Confirmation:** Confirm receipt and support partial fulfilment.
- **Shelter Management:** Monitor occupied, reserved and available spaces.
- **Dashboards and Notifications:** View resource shortages, assignments and activity updates.
- **Live Coordination Map:** Display shared areas and opted-in participants connected through the server.
- **Offline Support:** Save help requests on a device and synchronize them after reconnecting.
- **Light and Dark Modes:** Use a responsive interface across desktop and mobile devices.

## User Roles

| Role | Responsibilities |
|---|---|
| **Administrator** | Approve officers, review reports and oversee platform activities. |
| **NGO / Relief Officer** | Coordinate supplies, assign volunteers and manage shelter capacity after approval. |
| **Volunteer** | Reserve supplies, manage assignments and submit delivery updates. |
| **Community / Donor** | Request assistance, offer resources and confirm receipt. |

## Delivery Workflow

**Assigned → In Progress → Awaiting Confirmation → Delivered**

## Technologies

**Frontend:** HTML5, CSS3 and vanilla JavaScript  
**Backend:** Python and Django  
**Database:** SQLite locally; PostgreSQL for hosted deployment  
**Offline Storage:** IndexedDB, Service Worker and Cache API

## Connectivity

RESILIO operates through a hosted server or a reachable laptop server on the same local Wi-Fi network. When the server is unavailable, users can access cached public information and save new requests for later synchronization.

The coordination map uses schematic positions and visual animation. Bluetooth communication, phone-to-phone mesh networking and communication between separate relief-center servers are future extensions.

## Project Purpose

Developed for the **Web & Internet Programming Lab**, RESILIO demonstrates interactive web design, secure authentication, role-based access, relational database management and accountable resource coordination.
