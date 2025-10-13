package main

import (
    "bufio"
    "context"
    "encoding/base64"
    "fmt"
    "io"
    "net/http"
    "os"
    "path/filepath"
    "strings"
    "sync"
    "time"
)

const (
    timeout         = 20 * time.Second
    maxWorkers      = 10
    maxLinesPerFile = 500
)

var fixedText = `#profile-title: base64:8J+GkyBHaXRodWIgfCBEYW5pYWwgU2FtYWRpIPCfkI0=
#profile-update-interval: 1
#support-url: https://github.com/Argh94/VpnConfigCollector
#profile-web-page-url: https://github.com/Argh94/VpnConfigCollector
`

var protocols = []string{"vmess", "vless", "trojan", "ss", "ssr", "hy2", "hysteria2", "tuic", "tuic5", "wireguard", "warp"}

var links = []string{
    "https://raw.githubusercontent.com/ALIILAPRO/v2rayNG-Config/main/sub.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/refs/heads/main/mci/sub_2.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/refs/heads/main/mci/sub_3.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/refs/heads/main/app/sub.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/refs/heads/main/mtn/sub_1.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/refs/heads/main/mtn/sub_2.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/refs/heads/main/mtn/sub_3.txt",
    "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/refs/heads/main/mtn/sub_4.txt",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    "https://raw.githubusercontent.com/jagger235711/V2rayCollector/main/results/mixed_tested.txt",
    "https://raw.githubusercontent.com/ssrsub/ssr/refs/heads/master/v2ray",
    "https://raw.githubusercontent.com/acymz/AutoVPN/refs/heads/main/data/V2.txt",
    "https://raw.githubusercontent.com/giromo/Collector2/refs/heads/main/bulk/b64_merge2.txt",
    "https://raw.githubusercontent.com/giromo/Collector2/refs/heads/main/bulk/b64_merge1.txt",
    "https://raw.githubusercontent.com/ts-sf/fly/main/v2",
}

var dirLinks = []string{
    "https://raw.githubusercontent.com/Rayan-Config/C-Sub/refs/heads/main/configs/proxy.txt",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.txt",
    "https://raw.githubusercontent.com/MahsaNetConfigTopic/config/refs/heads/main/xray_final.txt",
    "https://github.com/Epodonios/v2ray-configs/raw/main/All_Configs_Sub.txt",
    "https://github.com/mahdibland/V2RayAggregator/blob/master/Eternity.txt",
    "https://raw.githubusercontent.com/SoliSpirit/v2ray-configs/main/all_configs.txt",
    "https://raw.githubusercontent.com/10ium/multi-proxy-config-fetcher/refs/heads/main/configs/proxy_configs.txt",
    "https://raw.githubusercontent.com/Kwinshadow/TelegramV2rayCollector/main/sublinks/mix.txt",
    "https://raw.githubusercontent.com/miladtahanian/V2RayCFGDumper/main/config.txt",
    "https://raw.githubusercontent.com/MhdiTaheri/V2rayCollector/refs/heads/main/sub/mix",
    "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v1",
    "https://raw.githubusercontent.com/SamanGho/v2ray_collector/refs/heads/main/last_150.txt",
    "https://raw.githubusercontent.com/Epodonios/v2ray-configs/refs/heads/main/All_Configs_Sub.txt",
    "https://raw.githubusercontent.com/Surfboardv2ray/TGParse/main/configtg.txt",
    "https://raw.githubusercontent.com/skywrt/v2ray-configs/main/All_Configs.txt",
}

type Result struct {
    Content  string
    IsBase64 bool
}

func main() {
    fmt.Println("Starting V2Ray config aggregator...")

    base64Folder, err := ensureDirectoriesExist()
    if err != nil {
        fmt.Printf("Error creating directories: %v\n", err)
        return
    }

    client := &http.Client{
        Timeout: timeout,
        Transport: &http.Transport{
            MaxIdleConns:        100,
            MaxIdleConnsPerHost: 10,
            IdleConnTimeout:     30 * time.Second,
        },
    }

    fmt.Println("Fetching configurations from sources...")
    allConfigs := fetchAllConfigs(client, links, dirLinks)

    fmt.Println("Filtering configurations and removing duplicates...")
    originalCount := len(allConfigs)
    filteredConfigs := filterForProtocols(allConfigs, protocols)

    fmt.Printf("Found %d unique valid configurations\n", len(filteredConfigs))
    fmt.Printf("Removed %d duplicates\n", originalCount-len(filteredConfigs))

    protocolCounts := make(map[string]int)
    for _, config := range filteredConfigs {
        for _, protocol := range protocols {
            if strings.HasPrefix(config, protocol) {
                protocolCounts[protocol]++
                break
            }
        }
    }
    fmt.Println("Protocol counts in filtered configs:")
    for protocol, count := range protocolCounts {
        fmt.Printf("  %s: %d configs\n", protocol, count)
    }

    cleanExistingFiles(base64Folder)

    mainOutputFile := "All_Configs_Sub.txt"
    err = writeMainConfigFile(mainOutputFile, filteredConfigs)
    if err != nil {
        fmt.Printf("Error writing main config file: %v\n", err)
        return
    }

    fmt.Println("Splitting into smaller files...")
    err = splitIntoFiles(base64Folder, filteredConfigs)
    if err != nil {
        fmt.Printf("Error splitting files: %v\n", err)
        return
    }

    fmt.Println("Sorting configurations by country and protocol...")
    sortConfigs()
    sortByCountry()
    sortByProtocol()

    // حذف فایل‌های میانی

    fmt.Println("Configuration aggregation completed successfully!")
}

func ensureDirectoriesExist() (string, error) {
    base64Folder := "Base64"
    if err := os.MkdirAll(base64Folder, 0755); err != nil {
        return "", err
    }
    return base64Folder, nil
}

func fetchAllConfigs(client *http.Client, base64Links, textLinks []string) []string {
    var wg sync.WaitGroup
    resultChan := make(chan Result, len(base64Links)+len(textLinks))

    semaphore := make(chan struct{}, maxWorkers)

    for _, link := range base64Links {
        wg.Add(1)
        go func(url string) {
            defer wg.Done()
            semaphore <- struct{}{}
            defer func() { <-semaphore }()

            content := fetchAndDecodeBase64(client, url)
            if content != "" {
                resultChan <- Result{Content: content, IsBase64: true}
            }
        }(link)
    }

    for _, link := range textLinks {
        wg.Add(1)
        go func(url string) {
            defer wg.Done()
            semaphore <- struct{}{}
            defer func() { <-semaphore }()

            content := fetchText(client, url)
            if content != "" {
                resultChan <- Result{Content: content, IsBase64: false}
            }
        }(link)
    }

    go func() {
        wg.Wait()
        close(resultChan)
    }()

    var allConfigs []string
    for result := range resultChan {
        lines := strings.Split(strings.TrimSpace(result.Content), "\n")
        allConfigs = append(allConfigs, lines...)
    }

    return allConfigs
}

func fetchAndDecodeBase64(client *http.Client, url string) string {
    ctx, cancel := context.WithTimeout(context.Background(), timeout)
    defer cancel()

    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        fmt.Printf("Error creating request for %s: %v\n", url, err)
        return ""
    }

    resp, err := client.Do(req)
    if err != nil {
        fmt.Printf("Error fetching %s: %v\n", url, err)
        return ""
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        fmt.Printf("HTTP error for %s: status code %d\n", url, resp.StatusCode)
        return ""
    }

    body, err := io.ReadAll(resp.Body)
    if err != nil {
        fmt.Printf("Error reading response from %s: %v\n", url, err)
        return ""
    }

    decoded, err := decodeBase64(body)
    if err != nil {
        fmt.Printf("Error decoding base64 from %s: %v\n", url, err)
        return ""
    }

    return decoded
}

func fetchText(client *http.Client, url string) string {
    ctx, cancel := context.WithTimeout(context.Background(), timeout)
    defer cancel()

    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        fmt.Printf("Error creating request for %s: %v\n", url, err)
        return ""
    }

    resp, err := client.Do(req)
    if err != nil {
        fmt.Printf("Error fetching %s: %v\n", url, err)
        return ""
    }
    defer resp.Body.Close()

    if resp.StatusCode != http.StatusOK {
        fmt.Printf("HTTP error for %s: status code %d\n", url, resp.StatusCode)
        return ""
    }

    body, err := io.ReadAll(resp.Body)
    if err != nil {
        fmt.Printf("Error reading response from %s: %v\n", url, err)
        return ""
    }

    return string(body)
}

func decodeBase64(encoded []byte) (string, error) {
    encodedStr := string(encoded)
    if len(encodedStr)%4 != 0 {
        encodedStr += strings.Repeat("=", 4-len(encodedStr)%4)
    }

    decoded, err := base64.StdEncoding.DecodeString(encodedStr)
    if err != nil {
        return "", err
    }

    return string(decoded), nil
}

func filterForProtocols(data []string, protocols []string) []string {
    var filtered []string
    seen := make(map[string]bool)

    for _, line := range data {
        line = strings.TrimSpace(line)
        if line == "" {
            continue
        }

        if seen[line] {
            continue
        }

        for _, protocol := range protocols {
            if strings.HasPrefix(line, protocol) {
                filtered = append(filtered, line)
                seen[line] = true
                break
            }
        }
    }
    return filtered
}

func cleanExistingFiles(base64Folder string) {
    os.Remove("All_Configs_base64_Sub.txt")

    for i := 0; i < 20; i++ {
        os.Remove(fmt.Sprintf("Sub%d.txt", i))
        os.Remove(filepath.Join(base64Folder, fmt.Sprintf("Sub%d_base64.txt", i)))
    }
}

func writeMainConfigFile(filename string, configs []string) error {
    file, err := os.Create(filename)
    if err != nil {
        return err
    }
    defer file.Close()

    writer := bufio.NewWriter(file)
    defer writer.Flush()

    if _, err := writer.WriteString(fixedText); err != nil {
        return err
    }

    for _, config := range configs {
        if _, err := writer.WriteString(config + "\n"); err != nil {
            return err
        }
    }

    return nil
}

func splitIntoFiles(base64Folder string, configs []string) error {
    numFiles := (len(configs) + maxLinesPerFile - 1) / maxLinesPerFile

    reversedConfigs := make([]string, len(configs))
    for i, config := range configs {
        reversedConfigs[len(configs)-1-i] = config
    }

    for i := 0; i < numFiles; i++ {
        profileTitle := fmt.Sprintf("🆓 Git:giromo | Sub%🌐", i+1)
        encodedTitle := base64.StdEncoding.EncodeToString([]byte(profileTitle))
        customFixedText := fmt.Sprintf(`#profile-title: base64:%s
#profile-update-interval: 1
#support-url: https://github.com/Argh94/VpnConfigCollector
#profile-web-page-url: https://github.com/Argh94/VpnConfigCollector
`, encodedTitle)

        start := i * maxLinesPerFile
        end := start + maxLinesPerFile
        if end > len(reversedConfigs) {
            end = len(reversedConfigs)
        }

        filename := fmt.Sprintf("Sub%d.txt", i+1)
        if err := writeSubFile(filename, customFixedText, reversedConfigs[start:end]); err != nil {
            return err
        }

        content, err := os.ReadFile(filename)
        if err != nil {
            return err
        }

        base64Filename := filepath.Join(base64Folder, fmt.Sprintf("Sub%d_base64.txt", i+1))
        encodedContent := base64.StdEncoding.EncodeToString(content)
        if err := os.WriteFile(base64Filename, []byte(encodedContent), 0644); err != nil {
            return err
        }
    }

    return nil
}

func writeSubFile(filename, header string, configs []string) error {
    file, err := os.Create(filename)
    if err != nil {
        return err
    }
    defer file.Close()

    writer := bufio.NewWriter(file)
    defer writer.Flush()

    if _, err := writer.WriteString(header); err != nil {
        return err
    }

    for _, config := range configs {
        if _, err := writer.WriteString(config + "\n"); err != nil {
            return err
        }
    }

    return nil
}
