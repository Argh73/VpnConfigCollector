package main

import (
    "fmt"
    "image/color"
    "net"
    "os"
    "os/exec"
    "runtime"
    "sort"
    "strconv"
    "strings"
    "sync"
    "time"

    "fyne.io/fyne/v2"
    "fyne.io/fyne/v2/app"
    "fyne.io/fyne/v2/canvas"
    "fyne.io/fyne/v2/container"
    "fyne.io/fyne/v2/layout"
    "fyne.io/fyne/v2/theme"
    "fyne.io/fyne/v2/widget"
    "fyne.io/systray"
)

var (
    dnsProfiles = map[string][]string{
        "Shekan":     {"178.22.122.100", "185.51.200.2"},
        "Google":     {"8.8.8.8", "8.8.4.4"},
        "Electro":    {"78.157.42.101", "78.157.42.100"},
        "Begzar":     {"185.55.226.26", "185.55.225.25"},
        "Radar":      {"10.202.10.10", "10.202.10.11"},
        "Shellter":   {"94.103.125.157", "94.103.125.158"},
        "Beshkan":    {"181.41.194.177", "181.41.194.186"},
        "Shatel":     {"85.15.1.14", "85.15.1.15"},
        "Cloudflare": {"1.1.1.1", "1.0.0.1"},
    }

    a             fyne.App
    w             fyne.Window
    dnsSelect     *widget.Select
    statusText    *canvas.Text
    currentDNSLbl *canvas.Text
    pingLabels    = make(map[string]*canvas.Text)
    pingMutex     sync.Mutex
    
    // متغیرهای جدید برای ویژگی‌های جدید
    networkInfo   *NetworkInfo
    networkMutex  sync.Mutex
)

// ساختار جدید برای اطلاعات شبکه
type NetworkInfo struct {
    ActiveConnections []ConnectionInfo
    CurrentGateway    string
    CurrentDNS        string
}

type ConnectionInfo struct {
    Name     string
    Type     string
    State    string
    Device   string
    IPv4     string
    Gateway  string
    DNS      []string
}

var accent = color.NRGBA{R: 0x4f, G: 0xc3, B: 0xf7, A: 0xff}

type modernTheme struct{ fyne.Theme }

func (m modernTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color {
    switch name {
    case theme.ColorNamePrimary:
        return accent
    case theme.ColorNameButton:
        return color.NRGBA{R: 0x33, G: 0x99, B: 0x66, A: 0xff}
    case theme.ColorNameError:
        return color.NRGBA{R: 0xf2, G: 0x6c, B: 0x6c, A: 0xff}
    }
    return m.Theme.Color(name, variant)
}

func main() {
    // خودکار اجرا با دسترسی ادمین/روت
    restartWithPrivileges()

    a = app.New()
    a.Settings().SetTheme(modernTheme{theme.DefaultTheme()})

    w = a.NewWindow("IR DNS Jumper")
    w.Resize(fyne.NewSize(850, 550))
    w.CenterOnScreen()

    // System Tray
    systray.Run(onReady, onExit)

    title := canvas.NewText("IR DNS Jumper", accent)
    title.TextSize = 32
    title.TextStyle = fyne.TextStyle{Bold: true}
    title.Alignment = fyne.TextAlignCenter

    subtitle := canvas.NewText("سریع‌ترین راه تغییر DNS در ایران", color.NRGBA{R: 180, G: 180, B: 180, A: 255})
    subtitle.TextSize = 16
    subtitle.Alignment = fyne.TextAlignCenter

    // نمایش DNS فعلی
    currentDNSLbl = canvas.NewText("در حال بررسی DNS فعلی...", color.NRGBA{R: 100, G: 200, B: 255, A: 255})
    currentDNSLbl.TextSize = 15
    currentDNSLbl.Alignment = fyne.TextAlignCenter

    dnsSelect = widget.NewSelect(getProfileNames(), func(s string) {
        if s != "" {
            applyDNS(s)
        }
    })
    dnsSelect.PlaceHolder = "انتخاب پروفایل DNS"

    statusText = canvas.NewText("", color.White)
    statusText.TextSize = 16
    statusText.Alignment = fyne.TextAlignCenter

    // دکمه‌ها
    setBtn := widget.NewButtonWithIcon("اعمال", theme.ConfirmIcon(), func() {
        if dnsSelect.Selected == "" {
            setStatus("لطفاً یک پروفایل انتخاب کنید", color.NRGBA{R: 255, G: 150, B: 150, A: 255})
            return
        }
        applyDNS(dnsSelect.Selected)
    })
    setBtn.Importance = widget.HighImportance

    clearBtn := widget.NewButtonWithIcon("حذف DNS", theme.DeleteIcon(), func() {
        clearDNS()
    })
    clearBtn.Importance = widget.DangerImportance

    refreshBtn := widget.NewButtonWithIcon("به‌روزرسانی", theme.ViewRefreshIcon(), func() {
        go refreshCurrentDNS()
        go updatePings()
        go scanNetwork()
    })
    refreshBtn.Importance = widget.MediumImportance

    // نمایش پینگ
    pingContainer := container.NewVBox()
    go updatePings() // شروع پینگ اولیه

    // نمایش اطلاعات شبکه
    networkContainer := container.NewVBox()
    networkContainer.Add(canvas.NewText("در حال اسکن شبکه...", color.White))
    go scanNetwork()

    // محتوا
    form := container.NewVBox(
        widget.NewForm(
            widget.NewFormItem("", container.NewBorder(nil, nil,
                container.NewHBox(widget.NewIcon(theme.SettingsIcon()), widget.NewLabel("پروفایل:")),
                nil, dnsSelect,
            )),
        ),
        layout.NewSpacer(),
        container.NewCenter(container.NewHBox(setBtn, clearBtn, refreshBtn)),
        layout.NewSpacer(),
        currentDNSLbl,
        statusText,
        layout.NewSpacer(),
        widget.NewLabel("پینگ سرورها:"),
        pingContainer,
        layout.NewSpacer(),
        widget.NewLabel("اطلاعات شبکه:"),
        networkContainer,
    )

    card := widget.NewCard("", "", form)

    content := container.NewVBox(
        layout.NewSpacer(),
        title,
        subtitle,
        layout.NewSpacer(),
        card,
        layout.NewSpacer(),
    )

    w.SetContent(container.NewBorder(layout.NewSpacer(), layout.NewSpacer(), nil, nil, content))

    // هنگام باز شدن برنامه
    go func() {
        time.Sleep(500 * time.Millisecond)
        refreshCurrentDNS()
        updatePings()
        scanNetwork()
    }()

    w.SetCloseIntercept(func() {
        w.Hide()
    })

    w.ShowAndRun()
}

func onReady() {
    systray.SetTitle("DNS Jumper")
    systray.SetTooltip("IR DNS Jumper - تغییر سریع DNS")
    systray.SetIcon(getIconBytes())

    for name := range dnsProfiles {
        n := name // capture
        m := systray.AddMenuItem(n, "اعمال "+n)
        go func() {
            for range m.ClickedCh {
                applyDNS(n)
            }
        }()
    }

    systray.AddSeparator()
    clearItem := systray.AddMenuItem("حذف DNS", "بازگردانی به DHCP")
    go func() {
        for range clearItem.ClickedCh {
            clearDNS()
        }
    }()

    showItem := systray.AddMenuItem("نمایش پنجره", "باز کردن برنامه")
    quitItem := systray.AddMenuItem("خروج", "بستن کامل برنامه")

    go func() {
        for range showItem.ClickedCh {
            w.Show()
        }
        for range quitItem.ClickedCh {
            systray.Quit()
            a.Quit()
        }
    }()
}

func onExit() {}

func getIconBytes() []byte {
    // آیکن ساده آبی
    return []byte{
        0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
        // ... (می‌تونی یه آیکن 64x64 بذاری یا اینو نگه داری)
    }
    // یا از embed استفاده کن بعداً
    return fyne.CurrentApp().Icon().Content()
}

func applyDNS(profile string) {
    setStatus("در حال اعمال "+profile+"...", color.Yellow)
    if err := setDNS(dnsProfiles[profile]); err != nil {
        setStatus("خطا: "+err.Error(), color.NRGBA{R: 255, G: 80, B: 80, A: 255})
    } else {
        setStatus("DNS با موفقیت اعمال شد: "+profile, color.NRGBA{R: 80, G: 255, B: 80, A: 255})
        dnsSelect.SetSelected(profile)
        time.AfterFunc(2*time.Second, refreshCurrentDNS)
        time.AfterFunc(2*time.Second, scanNetwork)
    }
}

func clearDNS() {
    setStatus("در حال حذف DNS...", color.Yellow)
    if err := resetDNS(); err != nil {
        setStatus("خطا: "+err.Error(), color.NRGBA{R: 255, G: 80, B: 80, A: 255})
    } else {
        setStatus("DNS با موفقیت حذف شد", color.NRGBA{R: 80, G: 255, B: 80, A: 255})
        dnsSelect.SetSelected("")
        time.AfterFunc(2*time.Second, refreshCurrentDNS)
        time.AfterFunc(2*time.Second, scanNetwork)
    }
}

func refreshCurrentDNS() {
    current, _ := getCurrentDNS()
    fyne.CurrentApp().RunOnMainThread(func() {
        if current == "" {
            currentDNSLbl.Text = "DNS فعلی: DHCP (اتوماتیک)"
            currentDNSLbl.Color = color.NRGBA{R: 180, G: 180, B: 180, A: 255}
        } else {
            profile := findProfileByDNS(current)
            if profile != "" {
                currentDNSLbl.Text = fmt.Sprintf("DNS فعلی: %s (%s)", current, profile)
                currentDNSLbl.Color = accent
                dnsSelect.SetSelected(profile)
            } else {
                currentDNSLbl.Text = "DNS فعلی: " + current + " (نامشخص)"
                currentDNSLbl.Color = color.NRGBA{R: 255, G: 180, B: 0, A: 255}
            }
        }
        currentDNSLbl.Refresh()
    })
}

// تابع جدید: تست سرعت واقعی DNS با ping چندباره
func updatePings() {
    pingMutex.Lock()
    defer pingMutex.Unlock()

    results := make(map[string]string)
    var wg sync.WaitGroup

    for name, servers := range dnsProfiles {
        wg.Add(1)
        go func(n string, s []string) {
            defer wg.Done()
            avgPing := testDNSPerformance(s[0], 3) // 3 بار ping
            if avgPing < 0 {
                results[n] = "خاموش"
            } else if avgPing < 50 {
                results[n] = fmt.Sprintf("%dms", avgPing)
            } else if avgPing < 150 {
                results[n] = fmt.Sprintf("%dms", avgPing)
            } else {
                results[n] = fmt.Sprintf("%dms", avgPing)
            }
        }(name, servers)
    }

    wg.Wait()

    fyne.CurrentApp().RunOnMainThread(func() {
        container := container.NewVBox()
        names := make([]string, 0, len(results))
        for k := range results {
            names = append(names, k)
        }
        sort.Strings(names)

        for _, name := range names {
            lbl := canvas.NewText(fmt.Sprintf("• %s: %s", name, results[name]), color.White)
            if results[name] == "خاموش" {
                lbl.Color = color.NRGBA{R: 255, G: 100, B: 100, A: 255}
            } else if ms, _ := strconv.Atoi(strings.TrimSuffix(results[name], "ms")); ms < 50 {
                lbl.Color = color.NRGBA{R: 100, G: 255, B: 100, A: 255}
            } else if ms < 150 {
                lbl.Color = color.NRGBA{R: 255, G: 220, B: 100, A: 255}
            }
            container.Add(lbl)
            pingLabels[name] = lbl
        }

        // جایگزینی صحیح محتوا
        if len(w.Content().(*container.Border).Objects) > 4 {
            // پیدا کردن container ping
            mainCard := w.Content().(*container.Border).Objects[1].(*widget.Card)
            if form, ok := mainCard.Content.(*container.Box); ok {
                for i, obj := range form.Objects {
                    if i < len(form.Objects) && obj.String() == "*container.Box" {
                        // این شناسایی دقیق نیست، پس از طریق والدین برویم
                        if box, ok := obj.(*container.Box); ok && len(box.Objects) > 7 {
                            box.Objects[7] = container
                            box.Refresh()
                            break
                        }
                    }
                }
            }
        }
    })
}

// تابع جدید: تست سرعت DNS با چندین ping
func testDNSPerformance(ip string, attempts int) int {
    var totalPing int
    successfulPings := 0
    
    for i := 0; i < attempts; i++ {
        start := time.Now()
        conn, err := net.DialTimeout("tcp", ip+":53", 2*time.Second)
        if err != nil {
            continue
        }
        conn.Close()
        pingTime := int(time.Since(start).Milliseconds())
        totalPing += pingTime
        successfulPings++
    }
    
    if successfulPings == 0 {
        return -1 // خاموش
    }
    
    return totalPing / successfulPings
}

// تابع جدید: اسکن شبکه و نمایش اتصالات فعال
func scanNetwork() {
    networkMutex.Lock()
    defer networkMutex.Unlock()
    
    info := &NetworkInfo{
        ActiveConnections: []ConnectionInfo{},
    }
    
    switch runtime.GOOS {
    case "linux":
        info.ActiveConnections = scanLinuxConnections()
        info.CurrentGateway = getCurrentGateway()
    case "windows":
        info.ActiveConnections = scanWindowsConnections()
        info.CurrentGateway = getCurrentGateway()
    }
    
    currentDNS, _ := getCurrentDNS()
    info.CurrentDNS = currentDNS
    
    networkInfo = info
    
    fyne.CurrentApp().RunOnMainThread(func() {
        updateNetworkDisplay()
    })
}

// تابع جدید: اسکن اتصالات لینوکس
func scanLinuxConnections() []ConnectionInfo {
    var connections []ConnectionInfo
    
    // دریافت لیست اتصالات فعال
    cmd := exec.Command("sh", "-c", 
        `nmcli -t -f NAME,TYPE,STATE,DEVICE con show --active`)
    output, err := cmd.Output()
    if err != nil {
        return connections
    }
    
    lines := strings.Split(strings.TrimSpace(string(output)), "\n")
    for _, line := range lines {
        if line == "" {
            continue
        }
        
        parts := strings.Split(line, ":")
        if len(parts) >= 4 {
            conn := ConnectionInfo{
                Name:  parts[0],
                Type:  parts[1],
                State: parts[2],
                Device: parts[3],
            }
            
            // دریافت IPv4 و DNS برای این اتصال
            conn.IPv4 = getConnectionIPv4(conn.Name)
            conn.Gateway = getConnectionGateway(conn.Name)
            conn.DNS = getConnectionDNS(conn.Name)
            
            connections = append(connections, conn)
        }
    }
    
    return connections
}

// تابع جدید: اسکن اتصالات ویندوز
func scanWindowsConnections() []ConnectionInfo {
    var connections []ConnectionInfo
    
    // دریافت اتصالات فعال ویندوز
    cmd := exec.Command("powershell", "-Command",
        `Get-NetConnectionProfile | Select-Object -Property Name,InterfaceAlias,NetworkCategory | ConvertTo-Json`)
    output, err := cmd.Output()
    if err != nil {
        return connections
    }
    
    // پردازش JSON خروجی (ساده)
    lines := strings.Split(string(output), "\n")
    for _, line := range lines {
        if strings.Contains(line, "InterfaceAlias") {
            // استخراج اسم اتصال
            parts := strings.Split(line, ":")
            if len(parts) > 1 {
                name := strings.Trim(strings.Trim(parts[1], "\""), ",")
                conn := ConnectionInfo{
                    Name:   name,
                    Type:   "Ethernet/WiFi",
                    State:  "Active",
                    Device: name,
                }
                
                // دریافت IPv4 و DNS
                conn.IPv4 = getWindowsIPv4(name)
                conn.Gateway = getWindowsGateway(name)
                conn.DNS = getWindowsDNS(name)
                
                connections = append(connections, conn)
            }
        }
    }
    
    return connections
}

// توابع کمکی برای لینوکس
func getConnectionIPv4(name string) string {
    cmd := exec.Command("sh", "-c", 
        fmt.Sprintf(`nmcli -g IP4.ADDRESS con show "%s"`, name))
    output, err := cmd.Output()
    if err != nil {
        return ""
    }
    return strings.TrimSpace(string(output))
}

func getConnectionGateway(name string) string {
    cmd := exec.Command("sh", "-c", 
        fmt.Sprintf(`nmcli -g IP4.GATEWAY con show "%s"`, name))
    output, err := cmd.Output()
    if err != nil {
        return ""
    }
    return strings.TrimSpace(string(output))
}

func getConnectionDNS(name string) []string {
    cmd := exec.Command("sh", "-c", 
        fmt.Sprintf(`nmcli -g IP4.DNS con show "%s"`, name))
    output, err := cmd.Output()
    if err != nil {
        return []string{}
    }
    
    dnsStr := strings.TrimSpace(string(output))
    if dnsStr == "" {
        return []string{}
    }
    
    return strings.Split(dnsStr, ",")
}

// توابع کمکی برای ویندوز
func getWindowsIPv4(name string) string {
    cmd := exec.Command("powershell", "-Command",
        fmt.Sprintf(`Get-NetIPAddress -InterfaceAlias "%s" -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress`, name))
    output, err := cmd.Output()
    if err != nil {
        return ""
    }
    return strings.TrimSpace(string(output))
}

func getWindowsGateway(name string) string {
    cmd := exec.Command("powershell", "-Command",
        fmt.Sprintf(`Get-NetRoute -InterfaceAlias "%s" -DestinationPrefix "0.0.0.0/0" | Select-Object -ExpandProperty NextHop`, name))
    output, err := cmd.Output()
    if err != nil {
        return ""
    }
    return strings.TrimSpace(string(output))
}

func getWindowsDNS(name string) []string {
    cmd := exec.Command("powershell", "-Command",
        fmt.Sprintf(`Get-DnsClientServerAddress -InterfaceAlias "%s" | Select-Object -ExpandProperty ServerAddresses`, name))
    output, err := cmd.Output()
    if err != nil {
        return []string{}
    }
    
    dnsStr := strings.TrimSpace(string(output))
    if dnsStr == "" {
        return []string{}
    }
    
    return strings.Split(dnsStr, " ")
}

// تابع جدید: دریافت گیتوی فعلی
func getCurrentGateway() string {
    switch runtime.GOOS {
    case "linux":
        cmd := exec.Command("sh", "-c", 
            `ip route get 1.1.1.1 | grep -oP 'via \K\S+'`)
        output, err := cmd.Output()
        if err != nil {
            return ""
        }
        return strings.TrimSpace(string(output))
        
    case "windows":
        cmd := exec.Command("powershell", "-Command",
            `Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Select-Object -ExpandProperty NextHop`)
        output, err := cmd.Output()
        if err != nil {
            return ""
        }
        return strings.TrimSpace(string(output))
        
    default:
        return ""
    }
}

// تابع جدید: به‌روزرسانی نمایش اطلاعات شبکه
func updateNetworkDisplay() {
    if networkInfo == nil {
        return
    }
    
    container := container.NewVBox()
    
    // نمایش گیتوی فعلی
    if networkInfo.CurrentGateway != "" {
        gatewayText := canvas.NewText(fmt.Sprintf("گیتوی فعلی: %s", networkInfo.CurrentGateway), color.White)
        container.Add(gatewayText)
    }
    
    // نمایش DNS فعلی
    if networkInfo.CurrentDNS != "" {
        dnsText := canvas.NewText(fmt.Sprintf("DNS فعلی: %s", networkInfo.CurrentDNS), color.White)
        container.Add(dnsText)
    }
    
    container.Add(canvas.NewText("", color.White)) // فاصله
    
    // نمایش اتصالات فعال
    for _, conn := range networkInfo.ActiveConnections {
        connText := canvas.NewText(fmt.Sprintf("اتصال: %s (%s)", conn.Name, conn.Type), accent)
        connText.TextStyle = fyne.TextStyle{Bold: true}
        container.Add(connText)
        
        if conn.Device != "" {
            deviceText := canvas.NewText(fmt.Sprintf("  دستگاه: %s", conn.Device), color.White)
            container.Add(deviceText)
        }
        
        if conn.State != "" {
            stateText := canvas.NewText(fmt.Sprintf("  وضعیت: %s", conn.State), color.White)
            container.Add(stateText)
        }
        
        if conn.IPv4 != "" {
            ipText := canvas.NewText(fmt.Sprintf("  IPv4: %s", conn.IPv4), color.White)
            container.Add(ipText)
        }
        
        if conn.Gateway != "" {
            gatewayText := canvas.NewText(fmt.Sprintf("  گیتوی: %s", conn.Gateway), color.White)
            container.Add(gatewayText)
        }
        
        if len(conn.DNS) > 0 {
            dnsText := canvas.NewText(fmt.Sprintf("  DNS: %s", strings.Join(conn.DNS, ", ")), color.White)
            container.Add(dnsText)
        }
        
        container.Add(canvas.NewText("", color.White)) // فاصله
    }
    
    // جایگزینی محتوای شبکه
    if len(w.Content().(*container.Border).Objects) > 4 {
        mainCard := w.Content().(*container.Border).Objects[1].(*widget.Card)
        if form, ok := mainCard.Content.(*container.Box); ok && len(form.Objects) > 9 {
            form.Objects[9] = container
            form.Refresh()
        }
    }
}

func pingServer(ip string) int {
    start := time.Now()
    conn, err := net.DialTimeout("tcp", ip+":53", 2*time.Second)
    if err != nil {
        return -1
    }
    conn.Close()
    return int(time.Since(start).Milliseconds())
}

func setStatus(msg string, col color.Color) {
    fyne.CurrentApp().RunOnMainThread(func() {
        statusText.Text = msg
        statusText.Color = col
        statusText.Refresh()
    })
}

func getProfileNames() []string {
    names := make([]string, 0, len(dnsProfiles))
    for k := range dnsProfiles {
        names = append(names, k)
    }
    sort.Strings(names)
    return names
}

func findProfileByDNS(dns string) string {
    for name, servers := range dnsProfiles {
        for _, s := range servers {
            if s == dns {
                return name
            }
        }
    }
    return ""
}

// تابع دریافت DNS فعلی (ویندوز + لینوکس)
func getCurrentDNS() (string, error) {
    switch runtime.GOOS {
    case "windows":
        cmd := exec.Command("powershell", "-Command",
            `(Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"} | Select-Object -First 1).ServerAddresses | Select-Object -First 1`)
        out, err := cmd.Output()
        if err != nil {
            return "", err
        }
        return strings.TrimSpace(string(out)), nil

    case "linux":
        // سعی می‌کنیم از nmcli استفاده کنیم
        cmd := exec.Command("sh", "-c",
            `nmcli -t -f IP4.DNS dev show "$(ip route get 1.1.1.1 | grep -oP 'dev \K\S+' | head -n1)" 2>/dev/null | head -n1 | cut -d: -f2`)
        out, err := cmd.Output()
        if err != nil || len(strings.TrimSpace(string(out))) == 0 {
            // fallback به resolv.conf
            data, _ := os.ReadFile("/etc/resolv.conf")
            for _, line := range strings.Split(string(data), "\n") {
                if strings.HasPrefix(line, "nameserver ") {
                    ip := strings.TrimSpace(strings.TrimPrefix(line, "nameserver "))
                    if net.ParseIP(ip) != nil && ip != "127.0.0.1" && ip != "127.0.0.53" {
                        return ip, nil
                    }
                }
            }
        }
        return strings.TrimSpace(string(out)), nil

    default:
        return "", fmt.Errorf("سیستم عامل پشتیبانی نمی‌شود")
    }
}

// اعمال DNS (همان قبلی با کمی بهبود)
func setDNS(servers []string) error {
    var cmd *exec.Cmd
    switch runtime.GOOS {
    case "linux":
        strServers := strings.Join(servers, " ")
        activeConn := getActiveConnectionName()
        if activeConn == "" {
            return fmt.Errorf("اتصال فعال پیدا نشد")
        }
        cmd = exec.Command("sh", "-c",
            fmt.Sprintf(`nmcli con mod "%s" ipv4.dns "%s" ipv4.ignore-auto-dns yes && nmcli con up "%s"`, activeConn, strServers, activeConn))

    case "windows":
        strServers := formatPSArray(servers)
        cmd = exec.Command("powershell", "-Command",
            fmt.Sprintf("Set-DnsClientServerAddress -InterfaceAlias (Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Select-Object -First 1).InterfaceAlias -ServerAddresses (%s)", strServers))

    default:
        return fmt.Errorf("سیستم عامل پشتیبانی نمی‌شود")
    }
    return cmd.Run()
}

// حذف DNS و بازگشت به حالت خودکار
func resetDNS() error {
    var cmd *exec.Cmd
    switch runtime.GOOS {
    case "linux":
        activeConn := getActiveConnectionName()
        if activeConn == "" {
            return fmt.Errorf("اتصال فعال پیدا نشد")
        }
        cmd = exec.Command("sh", "-c",
            fmt.Sprintf(`nmcli con mod "%s" ipv4.dns "" ipv4.ignore-auto-dns no && nmcli con up "%s"`, activeConn, activeConn))

    case "windows":
        cmd = exec.Command("powershell", "-Command",
            "Set-DnsClientServerAddress -InterfaceAlias (Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Select-Object -First 1).InterfaceAlias -ResetServerAddresses")

    default:
        return fmt.Errorf("سیستم عامل پشتیبانی نمی‌شود")
    }
    return cmd.Run()
}

// دریافت نام اتصال فعال در لینوکس - اصلاح شده
func getActiveConnectionName() string {
    cmd := exec.Command("sh", "-c",
        `nmcli -t -f NAME,DEVICE con show --active | grep "$(ip route get 1.1.1.1 | grep -oP 'dev \K\S+' | head -n1)" | cut -d: -f1`)
    out, err := cmd.Output()
    if err != nil {
        return ""
    }
    return strings.TrimSpace(string(out))
}

// فرمت کردن آرایه برای PowerShell
func formatPSArray(servers []string) string {
    quoted := make([]string, len(servers))
    for i, s := range servers {
        quoted[i] = fmt.Sprintf("'%s'", s)
    }
    return strings.Join(quoted, ",")
}

// اجرای خودکار با دسترسی ادمین/روت
func restartWithPrivileges() {
    if !hasElevatedPrivileges() {
        var cmd *exec.Cmd
        switch runtime.GOOS {
        case "windows":
            exe, _ := os.Executable()
            cmd = exec.Command("powershell", "Start-Process", exe, "-Verb", "RunAs")
        case "linux":
            exe, _ := os.Executable()
            cmd = exec.Command("pkexec", exe)
        default:
            return
        }
        cmd.Stdin = os.Stdin
        cmd.Stdout = os.Stdout
        cmd.Stderr = os.Stderr
        cmd.Run()
        os.Exit(0)
    }
}

// بررسی اینکه آیا برنامه با دسترسی بالا اجرا شده
func hasElevatedPrivileges() bool {
    switch runtime.GOOS {
    case "windows":
        cmd := exec.Command("net", "session")
        return cmd.Run() == nil
    case "linux":
        return os.Geteuid() == 0
    default:
        return true
    }
}
