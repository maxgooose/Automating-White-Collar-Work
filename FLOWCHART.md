# Finale Inventory Transfer Automation - System Flowchart

## Main Application Flow

```mermaid
flowchart TD
    subgraph User["👤 User Interface"]
        Start[Open Web Interface<br/>localhost:5000]
        Start --> Choice{Choose Method}
        
        Choice -->|Manual Entry| Manual[Manual Transfer Panel]
        Choice -->|Batch Upload| Batch[Excel Upload Panel]
    end

    subgraph ManualFlow["📝 Manual Transfer"]
        Manual --> EnterFrom[Enter FROM Location]
        EnterFrom --> EnterTo[Enter TO Location]
        EnterTo --> EnterIMEI[Enter IMEI/Barcode]
        EnterIMEI --> ExecuteBtn[Click Execute]
    end

    subgraph BatchFlow["📊 Batch Transfer"]
        Batch --> Upload[Upload Excel File<br/>.xlsx/.xls]
        Upload --> Parse[Parse Excel:<br/>Row 1: FROM, TO<br/>Column C: IMEIs]
        Parse --> Preview[Preview Transfer List]
        Preview --> ExecuteAll[Click Execute All]
    end

    subgraph ADB["📱 Android Automation via ADB"]
        ExecuteBtn --> ADBStart
        ExecuteAll --> ADBStart
        
        ADBStart[Connect to Device] --> NavTransfer[Navigate to Transfer Menu]
        NavTransfer --> TapMore[Tap MORE Button]
        TapMore --> TapTransfer[Tap '6. Transfer']
        TapTransfer --> TapTransferFrom[Tap '3. Transfer from']
        
        TapTransferFrom --> TypeFrom[Type FROM Location]
        TypeFrom --> PressEnter1[Press ENTER]
        PressEnter1 --> TypeTo[Type TO Location]
        TypeTo --> PressEnter2[Press ENTER]
        
        PressEnter2 --> ScanLoop{More IMEIs?}
        ScanLoop -->|Yes| TypeIMEI[Type IMEI]
        TypeIMEI --> PressEnter3[Press ENTER]
        PressEnter3 --> Wait[Wait for Sync<br/>~2 seconds]
        Wait --> ScanLoop
        
        ScanLoop -->|No| ExitMenu[Tap MENU Button]
        ExitMenu --> ExitMain[Tap 'Exit to Main Menu']
    end

    subgraph Result["✅ Completion"]
        ExitMain --> Success[Transfer Complete!]
        Success --> UpdateUI[Update Web Interface]
        UpdateUI --> Done[Done]
    end

    style Start fill:#4CAF50,color:#fff
    style Success fill:#2196F3,color:#fff
    style Done fill:#9C27B0,color:#fff
```

---

## Batch Execution Control Flow

```mermaid
flowchart TD
    BatchStart[Start Batch] --> SetupLoc[Setup Locations Once]
    SetupLoc --> Loop[Process IMEI Loop]
    
    Loop --> CheckPause{Paused?}
    CheckPause -->|Yes| WaitResume[Wait for Resume]
    WaitResume --> CheckStop1{Stopped?}
    CheckStop1 -->|No| CheckPause
    CheckStop1 -->|Yes| Abort[Abort & Return to Menu]
    
    CheckPause -->|No| CheckStop2{Stopped?}
    CheckStop2 -->|Yes| Abort
    CheckStop2 -->|No| ProcessIMEI[Scan Current IMEI]
    
    ProcessIMEI --> UpdateProgress[Update Progress<br/>Send to Web UI]
    UpdateProgress --> MoreItems{More IMEIs?}
    MoreItems -->|Yes| Loop
    MoreItems -->|No| Complete[Batch Complete]
    
    Complete --> ReturnMenu[Return to Main Menu]
    Abort --> ReturnMenu
    
    style BatchStart fill:#FF9800,color:#fff
    style Complete fill:#4CAF50,color:#fff
    style Abort fill:#f44336,color:#fff
```

---

## Finale App Screen Navigation

```mermaid
flowchart LR
    subgraph MainMenu["Main Menu"]
        M1[1. Sync]
        M2[2. Pick]
        M3[3. Receive]
        M4[4. Stock change]
        MORE[MORE ▶]
    end

    subgraph Page2["Page 2"]
        M5[5. ...]
        M6[6. Transfer]
        M7[7. ...]
        M8[8. ...]
    end

    subgraph TransferMenu["Transfer Menu"]
        T1[1. Transfer quick]
        T2[2. Transfer to]
        T3[3. Transfer from]
        T4[4. Transfer items]
    end

    subgraph TransferScreen["Transfer From Screen"]
        FROM[Enter FROM Location]
        TO[Enter TO Location]
        SCAN[Scan IMEIs...]
        MENU[MENU Button]
    end

    MORE -->|Tap| Page2
    M6 -->|Tap| TransferMenu
    T3 -->|Tap| TransferScreen
    MENU -->|Exit| MainMenu

    style M6 fill:#2196F3,color:#fff
    style T3 fill:#4CAF50,color:#fff
```

---

## System Architecture

```mermaid
flowchart TB
    subgraph Frontend["🌐 Web Frontend"]
        HTML[transferer.html]
        JS[JavaScript Client]
    end

    subgraph Backend["🖥️ Flask Server"]
        Server[transferer_server.py<br/>Port 5000]
        Routes["/upload<br/>/execute<br/>/execute-batch<br/>/status<br/>/pause<br/>/stop"]
    end

    subgraph Controller["🤖 Android Controller"]
        Auto[FinaleAutomator]
        ADB[ADB Commands]
    end

    subgraph Device["📱 Android Device"]
        Finale[Finale Inventory App]
        Screen[SurfaceView<br/>Custom Rendering]
    end

    HTML <-->|HTTP| Server
    JS <-->|SSE Status Stream| Routes
    Server --> Auto
    Auto -->|Shell Commands| ADB
    ADB -->|tap/type/swipe| Screen
    Screen --> Finale

    style HTML fill:#E91E63,color:#fff
    style Server fill:#3F51B5,color:#fff
    style Auto fill:#009688,color:#fff
    style Finale fill:#FF5722,color:#fff
```

---

## Quick Scripts Flow

```mermaid
flowchart TD
    subgraph Barcodes["type_barcodes.py"]
        B1[Read receive.txt] --> B2[For each IMEI]
        B2 --> B3[Type IMEI via ADB]
        B3 --> B4[Press ENTER]
        B4 --> B5{More IMEIs?}
        B5 -->|Yes| B2
        B5 -->|No| B6[Done!]
    end

    subgraph ItemState["type_itemState.py"]
        I1[Read receive.txt] --> I2[For each IMEI]
        I2 --> I3[Type IMEI via ADB]
        I3 --> I4[Press ENTER]
        I4 --> I5{Every 2nd IMEI?}
        I5 -->|Yes| I6[Tap CONFIRM Button]
        I6 --> I7{More IMEIs?}
        I5 -->|No| I7
        I7 -->|Yes| I2
        I7 -->|No| I8[Done!]
    end

    style B6 fill:#4CAF50,color:#fff
    style I8 fill:#4CAF50,color:#fff
```

---

## Data Flow

```mermaid
flowchart LR
    Excel[📄 Excel File<br/>.xlsx] -->|Upload| Server[🖥️ Flask]
    Server -->|Parse| Data[FROM, TO, IMEIs]
    Data -->|Store| Pending[Pending Batch]
    Pending -->|Execute| ADB[📱 ADB]
    ADB -->|Type| Finale[Finale App]
    
    TXT[📄 receive.txt] -->|Read| Script[🐍 Python Script]
    Script -->|Type| ADB

    style Excel fill:#217346,color:#fff
    style TXT fill:#FFD700,color:#000
    style Finale fill:#FF5722,color:#fff
```

---

## Key Coordinates (2400x1080 Landscape)

| Element | X | Y |
|---------|---|---|
| Back/Clear Button | 120 | 950 |
| Enter Button | 390 | 950 |
| More/Menu Button | 660 | 950 |
| Menu Item 1 | 400 | 185 |
| Menu Item 2 | 400 | 280 |
| Menu Item 3 | 400 | 375 |
| Menu Item 4 | 400 | 470 |
| Confirm Dialog - Back | 245 | 580 |
| Confirm Dialog - Confirm | 1310 | 580 |

---

*Generated for Project Manager presentation*

