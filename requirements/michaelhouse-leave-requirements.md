# **Functional Requirements Document (FRD)**

## **AI-Powered School Leave Application System**

| Document Version | 1.4 |
| :---- | :---- |
| Creation Date | November 2025 |
| Target Audience | Claude Code Development Team |

## **1\. Introduction**

### **1.1 Purpose and Scope**

This document defines the functional requirements for an AI-powered system designed to process and manage student leave applications for a boys' boarding school. The system will primarily interface with parents via external communication channels (WhatsApp and Email) and utilize specific tool calls for authentication, student linkage, and leave management.

### **1.2 System Context**

The core system is an AI Agent that receives unstructured text requests and uses a suite of predefined data access tools to validate, process, and record the leave.

## **2\. User Roles and Access**

| Role | Description | Access Channels | Data Access & Actions |
| :---- | :---- | :---- | :---- |
| **Parent** | Request leave for their son(s). | WhatsApp, Email | Request leave, receive approval/rejection notification. |
| **AI Agent** | Core processing engine. | Internal Tools (Read/Write), WhatsApp/Email (Send/Receive) | All Tool Calls, Communication. |
| **Housemaster** | Approves special leave requests, queries student leave data, cancels approved leaves, and imposes weekend restrictions. | WhatsApp, Email (Send/Receive) | Query student data, approve/reject special leave, cancel approved leave, set restrictions. |
| **Administrator** | Manages term dates and closed weekend configurations. | (Implied Admin UI/Tool Access \- **FR7**) | Configuration of term and block data. |
| **Guard** | Checks approved leave at the gate and marks student departure. | Dedicated Mobile App (Flutter) | Read approved leave register, update departure status. |

## **3\. Functional Requirements (FRs)**

### **FR1: Channel Interaction and Parsing**

| ID | Description | Details |
| :---- | :---- | :---- |
| **FR1.1** | **Input Channel Monitoring** | The system SHALL actively monitor for inbound leave requests from two channels: Email and WhatsApp. |
| **FR1.2** | **Request Parsing** | The system SHALL accurately parse the inbound request to identify four key data points: 1\. Student's Name/Admin Number, 2\. Requested Leave Start Date/Time, 3\. Requested Leave End Date/Time, 4\. Requested Leave Type (e.g., "overnight," "day," or "special"). |
| **FR1.3** | **Sender Identification** | The system SHALL identify the sender's identifier: the originating phone number (WhatsApp) or the originating email address (Email). |

### **FR2: Parent Authentication and Student Linkage**

| ID | Description | Tool Used | Details |
| :---- | :---- | :---- | :---- |
| **FR2.1** | **WhatsApp Authentication** | Tool\_Parent\_Phone\_Check | The system SHALL use the originating phone number to call Tool\_Parent\_Phone\_Check to verify the sender is a known Parent. |
| **FR2.2** | **Email Authentication** | Tool\_Parent\_Email\_Check | The system SHALL use the originating email address to call Tool\_Parent\_Email\_Check to verify the sender is a known Parent. |
| **FR2.3** | **Student/Parent Mapping** | Tool\_Student\_Parent\_Linkage | Upon successful parent authentication, the system SHALL call Tool\_Student\_Parent\_Linkage to confirm the requested student is a son of the authenticated parent. |
| **FR2.4** | **Rejection on Failure** | If authentication (FR2.1/FR2.2) or student mapping (FR2.3) fails, the system SHALL immediately reject the request and notify the sender via the originating channel (see FR6.2). |  |

### **FR3: Leave Eligibility and Rule Checks**

The system SHALL determine the type of leave and check its validity based on configuration data (Tool\_Term\_Config\_Read/Write) and student balances.

| ID | Description | Tool Used | Details/Rules |
| :---- | :---- | :---- | :---- |
| **FR3.1** | **Leave Type Classification** | N/A | The system SHALL classify the request into one of four types: 1\. Overnight Leave, 2\. Friday Supper Leave, 3\. Day Leave, 4\. Special Leave. |
| **FR3.2** | **Date Validity Check** | Tool\_Date\_Validity\_Check | The system SHALL check if the requested dates/times are valid against global term dates. |
| **FR3.3** | **Closed Weekend Check** | Tool\_Date\_Validity\_Check | If the student is in E Block or D Block, the system SHALL check if the requested dates fall on the first weekend of term or the weekend immediately after half term. If so, the request is routed for Special Leave (FR4.1). |
| **FR3.4** | **Check Overnight Balance** | Tool\_Leave\_Balance\_Check | If the request is for Overnight Leave (defined as Saturday post-sport to 18:50 Sunday), the system SHALL check the student has $\\ge 1$ of the **3 per term** allowance. |
| **FR3.5** | **Check Friday Supper Balance** | Tool\_Leave\_Balance\_Check | If the request is for Friday Supper Leave (defined as 17:00 to 21:00 Friday), the system SHALL check the student has $\\ge 1$ of the **3 per term** allowance. |
| **FR3.6** | **Day Leave Rule** | N/A | The system SHALL automatically approve Saturday and Sunday Day Leaves (non-overnight, assumed return before 17:00) as these are **unlimited**. No balance check is required. |
| **FR3.7** | **Restriction Check** | Tool\_Restriction\_Check | If the leave type is a weekend leave (Overnight, Supper, or Day Leave), the system SHALL call Tool\_Restriction\_Check. If the requested dates overlap with an active restriction period set by the Housemaster, the request SHALL be rejected (FR6.2). |

### **FR4: Special Leave Workflow**

Special leave is requested explicitly or triggered when a standard leave request falls on a closed weekend, or for an overnight period other than a Saturday night.

| ID | Description | Tool Used | Details |
| :---- | :---- | :---- | :---- |
| **FR4.1** | **Special Leave Trigger** | N/A | The system SHALL trigger the Special Leave workflow if: 1\) The parent explicitly requests "special leave," OR 2\) The requested leave falls on a closed weekend (E/D block only), OR 3\) The overnight leave is requested on a night other than Saturday to Sunday. |
| **FR4.2** | **Housemaster Routing** | N/A | The system SHALL automatically formulate an email containing the student's details, parent's details, and the requested leave dates, and send it to the relevant student's Housemaster for approval. |
| **FR4.3** | **Housemaster Response Processing** | N/A | The system SHALL monitor the Housemaster's email response. If the response indicates "Approve," processing continues (FR5.1). If "Reject," the rejection workflow is triggered (FR6.2). |

### **FR5: Processing, Balance Management, and Registration**

| ID | Description | Tool Used | Details |
| :---- | :---- | :---- | :---- |
| **FR5.1** | **Approval and Reduction** | Tool\_Leave\_Update | Upon final approval (either automated or by Housemaster), the system SHALL call Tool\_Leave\_Update to reduce the relevant leave balance (Overnight or Friday Supper) by **1**. (If Special Leave or Day Leave, no balance reduction is necessary). |
| **FR5.2** | **Leave Register Recording** | Tool\_Leave\_Update | Simultaneously with FR5.1, the system SHALL record the approved leave in the Leave Register. This record SHALL contain: **Leave Type, Date(s), Requesting Parent Name, Student Admin Number, Student First Name, Student Last Name, Student House, Student Block (Grade), and a null/unset field for Departure Timestamp.** |
| **FR5.3** | **Balance Reset** | N/A | The system SHALL ensure that leave balances (3 Overnight, 3 Friday Supper) are automatically reset at the start of each of the **4 terms per year**. |

### **FR6: Communication and Notification**

| ID | Description | Details |
| :---- | :---- | :---- |
| **FR6.1** | **Approval Notification** | The system SHALL inform the parent of leave approval via the **originating channel** (WhatsApp or Email). |
| **FR6.2** | **Rejection Notification** | The system SHALL inform the parent of leave rejection via the **originating channel** (WhatsApp or Email). The rejection notification **SHALL** clearly state the reason for rejection (e.g., authentication failure, insufficient balance, closed weekend, **student is currently restricted**). |
| **FR6.3** | **Special Leave Pending** | For Special Leave requests, the system SHALL inform the parent that the request has been forwarded to the Housemaster for manual review and approval, and that they will be notified upon decision. |
| **FR6.4** | **Cancellation Notification** | The system SHALL inform the parent via the **originating channel** when an approved leave is cancelled. The notification **MUST** include the cancellation reason and the identity of the Housemaster who initiated the cancellation. |

### **FR7: Administrative Configuration**

| ID | Description | Tool Used | Details |  
| \----- | \----- | \----- |  
| FR7.1 | Term Configuration | Tool\_Term\_Config\_Read/Write | The system SHALL provide a means for an Administrator to input and update the Start Date and End Date for each of the four terms annually. |  
| FR7.2 | Closed Weekend Configuration | \`Tool\_Term\_Config\_Read/Write\*\* | The system SHALL allow an Administrator to define and update the specific weekends that are closed for the E Block and D Block. This must include the first weekend of term and the weekend immediately after half term. |

### **FR8: Guard Gate Management Application (Flutter)**

This section defines requirements for the dedicated mobile application used by the Guard role.

| ID | Description | Tool Used | Details |
| :---- | :---- | :---- | :---- |
| **FR8.1** | **Guard Authentication** | N/A (Requires separate Guard/Staff Auth Tool) | The Guard SHALL be able to securely log in to the mobile application using assigned staff credentials. |
| **FR8.2** | **Student Lookup Interface** | N/A | The application SHALL provide a clear and simple input field for the Guard to enter a Student's Admin ID. |
| **FR8.3** | **Active Leave Status Retrieval** | Tool\_Leave\_Lookup | The application SHALL query the Leave Register using the Admin ID to retrieve all **approved, currently active, and unmarked as departed** leave entries. The lookup SHALL use the current time to filter active leave periods. |
| **FR8.4** | **Leave Confirmation Display** | N/A | If an active, approved leave is found, the application SHALL display the full leave details (Student Name, Leave Type, Start/End Date/Time, Requesting Parent). |
| **FR8.5** | **Departure Logging** | Tool\_Leave\_Update | If a valid leave is displayed, the application SHALL provide a "Confirm Departure" button. Clicking this button SHALL call Tool\_Leave\_Update to record the current date and time in the **Departure Timestamp** field for that specific leave entry. |
| **FR8.6** | **No Leave Status Display** | N/A | If no active, approved leave is found, the application SHALL display a clear, high-visibility message stating, "NO APPROVED LEAVE FOUND." |

### **FR9: Housemaster Query and Cancellation**

This section defines requirements for the Housemaster to actively manage leave and place student restrictions.

| ID | Description | Tool Used | Details |
| :---- | :---- | :---- | :---- |
| **FR9.1** | **Housemaster Authentication** | Tool\_HM\_Auth\_House\_Check | The system SHALL authenticate the Housemaster via their originating email/phone number and retrieve their assigned House and HM ID. |
| **FR9.2** | **Leave/Balance Query Processing** | Tool\_Leave\_Query\_HM | Upon successful authentication, the system SHALL process natural language queries from the Housemaster to retrieve: 1\) A list of all approved leaves for a student in their House, OR 2\) The current leave balance for a student in their House. |
| **FR9.3** | **Leave Cancellation Command** | N/A | The system SHALL parse Housemaster requests containing a clear intent to cancel a specific, approved leave, along with a mandatory cancellation reason. |
| **FR9.4** | **Cancellation Execution and Refund** | Tool\_Leave\_Update | Upon successful cancellation command, the system SHALL call Tool\_Leave\_Update to: 1\) Mark the original leave entry as 'Canceled', 2\) Record the Housemaster's ID and Cancellation Reason, AND 3\) **Refund the deducted leave balance** (by incrementing the relevant balance: Overnight or Friday Supper) ONLY if the leave type originally consumed a balance. |
| **FR9.5** | **Parent Notification (Cancellation)** | N/A | Following cancellation (FR9.4), the system SHALL trigger the Cancellation Notification workflow (FR6.4). |
| **FR9.6** | **Restriction Command** | N/A | The system SHALL parse Housemaster requests containing a clear intent to place a restriction on a student, including the **Admin ID, the Restriction Start Date, and the Restriction End Date**. |
| **FR9.7** | **Restriction Execution** | Tool\_Restriction\_Update | Upon successful restriction command, the system SHALL call Tool\_Restriction\_Update to log the restriction details (HM ID, Student Admin No, Start Date, End Date). The system SHALL confirm the restriction has been applied to the Housemaster. |

## **4\. Non-Functional Requirements (NFRs)**

This section outlines "nice to have" or quality requirements that are important for the system but not essential for its core operational function.

| ID | Description | Priority | Details |
| :---- | :---- | :---- | :---- |
| **NFR4.1** | **Driver ID Capture & Storage** | Nice-to-Have | The Guard Gate Management Application SHALL have the capability to use the device camera to scan a South African driver's license or capture an image of another form of photographic ID for the driver picking up the student. This captured image/data SHALL be stored as metadata against the corresponding leave record in the Leave Register. |
| **NFR4.2** | **System Responsiveness** | Performance | The AI Agent SHALL process and respond to standard (non-special) leave requests within 30 seconds. |
| **NFR4.3** | **Security** | Security | All sensitive data (parent/student details, authentication IDs, captured driver IDs) SHALL be encrypted both in transit and at rest. |

## **5\. Data Models and Tool Call Requirements**

The AI Agent and Guard App rely on the following tool calls to access system data.

| Tool Call | Purpose | Data Required for Query | Data Returned |
| :---- | :---- | :---- | :---- |
| Tool\_Parent\_Phone\_Check | Authenticate Parent by Phone | phoneNumber: string | parentAuthId: string or null |
| Tool\_Parent\_Email\_Check | Authenticate Parent by Email | emailAddress: string | parentAuthId: string or null |
| Tool\_Student\_Parent\_Linkage | Verify Student belongs to Parent | parentAuthId: string, requestedStudentIdentifier: string | studentRecord: object (Containing Admin No, Name, House, Block, Current Term Leave Balances) |
| Tool\_HM\_Auth\_House\_Check | Authenticate HM and map to House | identifier: string (phone or email) | hmID: string, assignedHouse: string or null |
| **Tool\_Restriction\_Check** | Check for active leave restrictions | studentAdminNumber: string, startDate: datetime, endDate: datetime | isRestricted: boolean |
| **Tool\_Restriction\_Update** | Set/Clear Student Leave Restriction | hmID: string, studentAdminNumber: string, startDate: datetime, endDate: datetime | success: boolean |
| Tool\_Date\_Validity\_Check | Check if dates are permissible | studentBlock: string, startDate: datetime, endDate: datetime | isValid: boolean, reason: string (e.g., "Falls on closed weekend") |
| Tool\_Leave\_Balance\_Check | Check remaining leave balance | studentAdminNumber: string, \`leaveType: 'Overnight' | 'Supper'\` |
| Tool\_Leave\_Query\_HM | Retrieve specific student leave/balance | hmID: string, studentAdminNumber: string | leaveDetails: object\[\] or balance: number |
| Tool\_Leave\_Update | Update register and balance / Log Departure / Log Driver ID / Log Cancellation | studentAdminNumber: string, leaveType: string, dateRange: object, requestingParent: string, departureTimestamp: datetime (optional), driverIDCapture: file/string (optional), cancellationDetails: object (optional) | success: boolean |
| Tool\_Leave\_Lookup | Retrieve Active Leave for Guard App | studentAdminNumber: string, currentTimestamp: datetime | activeLeaveRecord: object\[\] or null |
| Tool\_Term\_Config\_Read/Write | Term/Block Rules | Varies (e.g., getClosedWeekends('E')) | Term dates, closed weekend dates by block. |

### **Key Leave Definitions:**

| Leave Type | Period Definition | Term Limit |
| :---- | :---- | :---- |
| **Overnight Leave** | Valid after sport on Saturday to 18:50 on Sunday. | 3 per term |
| **Friday Supper Leave** | Valid from 17:00 to 21:00 on Friday. | 3 per term |
| **Saturday/Sunday Day Leave** | Any leave that is not Overnight or Friday Supper, and occurs only on a Saturday or Sunday, returning before 17:00. | Unlimited |
| **Special Leave** | Explicitly requested OR triggered by falling on a closed weekend (E/D block) OR requested for an overnight stay other than Sat to Sun. | N/A (Requires Housemaster Approval) |

