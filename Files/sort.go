package main

import (
    "bufio"
    "encoding/base64"
    "encoding/json"
    "fmt"
    "os"
    "path/filepath"
    "strings"
)

var (
    ignoreWords = []string{
        "test", "free", "premium", "vpn", "config", "v2ray", "v2rayng", "vless", "trojan", "shadowsocks",
        "ss", "ssr", "hysteria", "hy2", "tuic", "warp", "wireguard", "telegram", "channel", "group",
        "server", "net", "network", "fast", "speed", "high", "low", "ping", "ms", "http", "https",
        "tls", "reality", "grpc", "ws", "websocket", "tcp", "udp", "h2", "h3", "auto", "none", "random",
    }
    protocolPatterns = map[string][]string{
        "vless":       {"vless://"},
        "trojan":      {"trojan://"},
        "shadowsocks": {"ss://", "shadowsocks://"},
        "shadowsocksr": {"ssr://"},
        "vmess":       {"vmess://"},
        "tuic":        {"tuic://", "tuic5://"},
        "hysteria2":   {"hysteria2://", "hy2://"},
        "wireguard":   {"wg://", "wireguard://"},
        "warp":        {"warp://"},
    }
    countrySymbols map[string][]string
)

// تابع برای خواندن countrySymbols از فایل key.json
func loadCountrySymbols() error {
    file, err := os.Open("Files/key.json")
    if err != nil {
        return fmt.Errorf("error opening key.json: %v", err)
    }
    defer file.Close()

    var data struct {
        Countries map[string][]string `json:"countries"`
    }
    decoder := json.NewDecoder(file)
    if err := decoder.Decode(&data); err != nil {
        return fmt.Errorf("error decoding key.json: %v", err)
    }

    countrySymbols = data.Countries
    return nil
}

func identifyCountry(config string) string {
    configLower := strings.ToLower(config)
    for _, ignore := range ignoreWords {
        configLower = strings.ReplaceAll(configLower, ignore, "")
    }

    // مرحله 1: بررسی پرچم‌های emoji در remark
    flagToCountry := make(map[string]string)
    for country, symbols := range countrySymbols {
        for _, symbol := range symbols {
            if strings.HasPrefix(symbol, "🇦") || strings.HasPrefix(symbol, "🇧") ||
                strings.HasPrefix(symbol, "🇨") || strings.HasPrefix(symbol, "🇩") ||
                strings.HasPrefix(symbol, "🇪") || strings.HasPrefix(symbol, "🇫") ||
                strings.HasPrefix(symbol, "🇬") || strings.HasPrefix(symbol, "🇭") ||
                strings.HasPrefix(symbol, "🇮") || strings.HasPrefix(symbol, "🇯") ||
                strings.HasPrefix(symbol, "🇰") || strings.HasPrefix(symbol, "🇱") ||
                strings.HasPrefix(symbol, "🇲") || strings.HasPrefix(symbol, "🇳") ||
                strings.HasPrefix(symbol, "🇴") || strings.HasPrefix(symbol, "🇵") ||
                strings.HasPrefix(symbol, "🇶") || strings.HasPrefix(symbol, "🇷") ||
                strings.HasPrefix(symbol, "🇸") || strings.HasPrefix(symbol, "🇹") ||
                strings.HasPrefix(symbol, "🇺") || strings.HasPrefix(symbol, "🇻") ||
                strings.HasPrefix(symbol, "🇼") || strings.HasPrefix(symbol, "🇽") ||
                strings.HasPrefix(symbol, "🇾") || strings.HasPrefix(symbol, "🇿") {
                flagToCountry[symbol] = country
            }
        }
    }

    if idx := strings.Index(config, "#"); idx != -1 {
        remark := config[idx+1:]
        for flag, country := range flagToCountry {
            if strings.Contains(remark, flag) {
                fmt.Printf("Matched country %s by emoji flag in remark: %s\n", country, config[:50])
                return country
            }
        }
    }

    // مرحله 2: بررسی پرچم‌های emoji در query
    if idx := strings.Index(config, "?"); idx != -1 {
        query := config[idx+1:]
        for flag, country := range flagToCountry {
            if strings.Contains(query, flag) {
                fmt.Printf("Matched country %s by emoji flag in query: %s\n", country, config[:50])
                return country
            }
        }
    }

    // مرحله 3: بررسی نام‌های کشور در remark
    if idx := strings.Index(config, "#"); idx != -1 {
        remark := strings.ToLower(config[idx+1:])
        for country, symbols := range countrySymbols {
            for _, symbol := range symbols {
                symbolLower := strings.ToLower(symbol)
                // فقط کلمات کامل را بررسی کن
                if strings.Contains(" "+remark+" ", " "+symbolLower+" ") {
                    fmt.Printf("Matched country %s by symbol %s in remark: %s\n", country, symbol, config[:50])
                    return country
                }
            }
        }
    }

    // مرحله 4: بررسی فیلد ps در کانفیگ‌های Vmess
    if strings.HasPrefix(config, "vmess://") {
        encoded := strings.TrimPrefix(config, "vmess://")
        if len(encoded)%4 != 0 {
            encoded += strings.Repeat("=", 4-len(encoded)%4)
        }
        decoded, err := base64.StdEncoding.DecodeString(encoded)
        if err == nil {
            var vmess struct {
                Ps string `json:"ps"`
            }
            if err := json.Unmarshal(decoded, &vmess); err == nil && vmess.Ps != "" {
                psLower := strings.ToLower(vmess.Ps)
                for _, ignore := range ignoreWords {
                    psLower = strings.ReplaceAll(psLower, ignore, "")
                }
                for country, symbols := range countrySymbols {
                    for _, symbol := range symbols {
                        symbolLower := strings.ToLower(symbol)
                        // فقط کلمات کامل را بررسی کن
                        if strings.Contains(" "+psLower+" ", " "+symbolLower+" ") {
                            fmt.Printf("Matched country %s by symbol %s in Vmess ps: %s\n", country, symbol, config[:50])
                            return country
                        }
                    }
                }
            }
        }
    }

    fmt.Printf("No country matched, returning unknown: %s\n", config[:50])
    return "unknown"
}

func identifyProtocol(config string) string {
    for protocol, patterns := range protocolPatterns {
        for _, pattern := range patterns {
            if strings.HasPrefix(config, pattern) {
                return protocol
            }
        }
    }
    return "unknown"
}

func sortConfigs() {
    inputFile := "All_Configs_Sub.txt"
    outputFile := "All_Configs_Sorted.txt"

    file, err := os.Open(inputFile)
    if err != nil {
        fmt.Printf("Error opening input file: %v\n", err)
        return
    }
    defer file.Close()

    var configs []string
    scanner := bufio.NewScanner(file)
    for scanner.Scan() {
        line := strings.TrimSpace(scanner.Text())
        if line != "" && !strings.HasPrefix(line, "#") {
            configs = append(configs, line)
        }
    }

    if err := scanner.Err(); err != nil {
        fmt.Printf("Error reading input file: %v\n", err)
        return
    }

    seen := make(map[string]bool)
    var uniqueConfigs []string
    for _, config := range configs {
        if !seen[config] {
            seen[config] = true
            uniqueConfigs = append(uniqueConfigs, config)
        }
    }

    out, err := os.Create(outputFile)
    if err != nil {
        fmt.Printf("Error creating output file: %v\n", err)
        return
    }
    defer out.Close()

    writer := bufio.NewWriter(out)
    defer writer.Flush()

    if _, err := writer.WriteString(fixedText); err != nil {
        fmt.Printf("Error writing header: %v\n", err)
        return
    }

    for _, config := range uniqueConfigs {
        if _, err := writer.WriteString(config + "\n"); err != nil {
            fmt.Printf("Error writing config: %v\n", err)
            return
        }
    }

    fmt.Printf("Sorted %d unique configs into %s\n", len(uniqueConfigs), outputFile)
}

func sortByCountry() {
    inputFile := "All_Configs_Sorted.txt"
    outputDir := "Splitted-By-Country"

    if err := os.MkdirAll(outputDir, 0755); err != nil {
        fmt.Printf("Error creating output directory: %v\n", err)
        return
    }

    file, err := os.Open(inputFile)
    if err != nil {
        fmt.Printf("Error opening input file: %v\n", err)
        return
    }
    defer file.Close()

    countryFiles := make(map[string]*os.File)
    countryWriters := make(map[string]*bufio.Writer)
    countryConfigCount := make(map[string]int)

    scanner := bufio.NewScanner(file)
    for scanner.Scan() {
        line := strings.TrimSpace(scanner.Text())
        if line == "" || strings.HasPrefix(line, "#") {
            continue
        }

        country := identifyCountry(line)
        if country == "" {
            country = "unknown"
        }

        if _, ok := countryFiles[country]; !ok {
            filename := filepath.Join(outputDir, country+".txt")
            f, err := os.Create(filename)
            if err != nil {
                fmt.Printf("Error creating file for %s: %v\n", country, err)
                continue
            }
            countryFiles[country] = f
            countryWriters[country] = bufio.NewWriter(f)
            countryConfigCount[country] = 0
        }

        if _, err := countryWriters[country].WriteString(line + "\n"); err != nil {
            fmt.Printf("Error writing to %s: %v\n", country, err)
            continue
        }
        countryConfigCount[country]++
    }

    if err := scanner.Err(); err != nil {
        fmt.Printf("Error reading input file: %v\n", err)
    }

    for country, writer := range countryWriters {
        writer.Flush()
        countryFiles[country].Close()
        fmt.Printf("Wrote %d configs to %s.txt\n", countryConfigCount[country], country)
    }
}

func sortByProtocol() {
    inputFile := "All_Configs_Sorted.txt"
    outputDir := "Splitted-By-Protocol"

    if err := os.MkdirAll(outputDir, 0755); err != nil {
        fmt.Printf("Error creating output directory: %v\n", err)
        return
    }

    file, err := os.Open(inputFile)
    if err != nil {
        fmt.Printf("Error opening input file: %v\n", err)
        return
    }
    defer file.Close()

    protocolConfigs := make(map[string][]string)
    scanner := bufio.NewScanner(file)
    for scanner.Scan() {
        line := strings.TrimSpace(scanner.Text())
        if line == "" || strings.HasPrefix(line, "#") {
            continue
        }

        protocol := identifyProtocol(line)
        if protocol == "" {
            protocol = "unknown"
        }
        protocolConfigs[protocol] = append(protocolConfigs[protocol], line)
    }

    if err := scanner.Err(); err != nil {
        fmt.Printf("Error reading input file: %v\n", err)
    }

    for protocol, configs := range protocolConfigs {
        filename := filepath.Join(outputDir, fmt.Sprintf("%s.txt", protocol))
        f, err := os.Create(filename)
        if err != nil {
            fmt.Printf("Error creating file for %s: %v\n", protocol, err)
            continue
        }

        writer := bufio.NewWriter(f)
        for _, config := range configs {
            if _, err := writer.WriteString(config + "\n"); err != nil {
                fmt.Printf("Error writing to %s: %v\n", protocol, err)
                continue
            }
        }
        writer.Flush()
        f.Close()
        fmt.Printf("Wrote %d configs to %s\n", len(configs), filename)
    }
}

// تابع main یا init برای بارگذاری key.json
func init() {
    if err := loadCountrySymbols(); err != nil {
        fmt.Printf("Failed to load country symbols: %v\n", err)
        os.Exit(1)
    }
}
