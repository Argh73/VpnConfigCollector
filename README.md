# VpnConfigCollector

![Go](https://img.shields.io/badge/language-Go-blue.svg)
![GitHub repo size](https://img.shields.io/github/repo-size/giromo/Xrey-collector)
![GitHub last commit](https://img.shields.io/github/last-commit/giromo/Xrey-collector)
![GitHub issues](https://img.shields.io/github/issues/giromo/Xrey-collector)
![GitHub stars](https://img.shields.io/github/stars/giromo/Xrey-collector?style=social)

## معرفی پروژه

**Xrey-collector** یک ابزار متن‌باز به زبان Go است که وظیفه جمع‌آوری، پردازش، رمزگذاری و سازماندهی حجم زیادی از داده‌های کانفیگ یا سابسکریپشن را بر عهده دارد. این پروژه با هدف مدیریت پیشرفته فایل‌های تنظیمات سرورهای پراکسی یا سرویس‌های مشابه طراحی شده است و امکانات متعددی برای پردازش، تقسیم‌بندی و مدیریت این داده‌ها ارائه می‌کند.

---

## امکانات کلیدی

- **تجمع و یکپارچه‌سازی داده‌ها:** امکان جمع‌آوری و ادغام حجم بالایی از اطلاعات (نمونه: `All_Configs_Sub.txt`)
- **تقسیم‌بندی بر اساس پروتکل:** دسته‌بندی فایل‌ها بر اساس پروتکل‌های مختلف در پوشه `Splitted-By-Protocol`
- **پشتیبانی از رمزگذاری Base64:** ابزارها و اسکریپت‌هایی برای رمزگذاری و رمزگشایی داده‌ها در پوشه `Base64`
- **مدیریت فایل‌های بزرگ:** توانایی کار با ده‌ها فایل متنی حجیم (`Sub1.txt` تا `Sub52.txt`)
- **ابزار اجرایی:** وجود فایل اجرایی `aggregator` برای پردازش و جمع‌آوری داده‌ها

---

## لینک‌های اشتراک انواع پروتکل

<div align="center">

| نوع پروتکل | لینک‌های اشتراک                                                                                                           | نوع پروتکل | لینک‌های اشتراک                                                                                                           |
|:-----------:|:----------------------------------------------------------------------------------------------------------------------------|:-----------:|:----------------------------------------------------------------------------------------------------------------------------|
| Hy2         | [لینک](https://raw.githubusercontent.com/giromo/Xrey-collector/refs/heads/main/Splitted-By-Protocol/hy2.txt)                | Hysteria2   | [لینک](https://raw.githubusercontent.com/giromo/Xrey-collector/refs/heads/main/Splitted-By-Protocol/hysteria2.txt)          |
| SS          | [لینک](https://raw.githubusercontent.com/giromo/Xrey-collector/refs/heads/main/Splitted-By-Protocol/ss.txt)                 | SSR         | [لینک](https://raw.githubusercontent.com/giromo/Xrey-collector/refs/heads/main/Splitted-By-Protocol/ssr.txt)                |
| Trojan      | [لینک](https://raw.githubusercontent.com/giromo/Xrey-collector/refs/heads/main/Splitted-By-Protocol/trojan.txt)             | Tuic        | [لینک](https://raw.githubusercontent.com/giromo/Xrey-collector/refs/heads/main/Splitted-By-Protocol/tuic.txt)               |
| Vless       | [لینک](https://raw.githubusercontent.com/giromo/Xrey-collector/refs/heads/main/Splitted-By-Protocol/vless.txt)              | Vmess       | [لینک](https://raw.githubusercontent.com/giromo/Xrey-collector/refs/heads/main/Splitted-By-Protocol/vmess.txt)              |
| Wireguard   | [لینک](https://raw.githubusercontent.com/giromo/Xrey-collector/refs/heads/main/Splitted-By-Protocol/wireguard.txt)          | Warp        | [لینک](https://raw.githubusercontent.com/giromo/Xrey-collector/refs/heads/main/Splitted-By-Protocol/warp.txt)               |

</div>

---


## Telegram-V2ray-Configs-Collector

This tool designed to collect and share V2Ray configs from Telegram channels this tool helps users bypass internet censorship and enhance their online privacy through various routing and encryption techniques.

**⚠️ Warning: The security of the collected V2ray configs is not guaranteed in any way please use to maintain your security in times of essential .**

**📌 Help us in the telegram channel list ( you can send us telegram channels to [Telegram](https://t.me/mohamaadfg) or in this repository ) .**

## Protocol Type Subscription Links

| Protocol Type | Subscription Links                                                                                                              | Protocol Type | Subscription Links                                                                                                           |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Vless         | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/refs/heads/main/category/vless.txt)     | Vmess         | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/refs/heads/main/category/vmess.txt)  |
| ShadowSocks   | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/refs/heads/main/category/ss.txt)        | Trojan        | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/refs/heads/main/category/trojan.txt) |
| Wireguard     | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/refs/heads/main/category/wireguard.txt) | Reality       | Comin soon!                                                                                                                  |
| Hysteria      | Comin soon!                                                                                                                     | Juicity       | Comin soon!                                                                                                                  |
| Tuic          | Comin soon!                                                                                                                     |

## Network Type Subscription Links

| Protocol Type | Subscription Links                                                                                              | Protocol Type | Subscription Links                                                                                                     |
| ------------- | --------------------------------------------------------------------------------------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------- |
| GRPC          | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/grpc.txt) | TCP           | [Link](https://github.com/mohamadfg-dev/telegram-v2ray-configs-collector/raw/refs/heads/main/category/httpupgrade.txt) |
| HTTP          | [Link](https://github.com/mohamadfg-dev/telegram-v2ray-configs-collector/raw/refs/heads/main/category/http.txt) | QUIC          | Comin soon!                                                                                                            |
| WS            | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/ws.txt)   |               |                                                                                                                        |

## Country Subscription Links

| Country Name              | Subscription Link                                                                                                                   | Country Name              | Subscription Link                                                                                                                 |
| :------------------------ | :---------------------------------------------------------------------------------------------------------------------------------- | :------------------------ | :-------------------------------------------------------------------------------------------------------------------------------- |
| 🇦🇱 Albania                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Albania.txt)                  | 🇦🇷 Argentina              | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Argentina.txt)              |
| 🇦🇲 Armenia                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Armenia.txt)                  | 🇦🇺 Australia              | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Australia.txt)              |
| 🇦🇹 Austria                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Austria.txt)                  | 🇧🇭 Bahrain                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Bahrain.txt)                |
| 🇧🇪 Belgium                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Belgium.txt)                  | 🇧🇴 Bolivia                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Bolivia.txt)                |
| 🇧🇦 Bosnia and Herzegovina | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Bosnia_and_Herzegovina.txt)   | 🇧🇷 Brazil                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Brazil.txt)                 |
| 🇧🇬 Bulgaria               | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Bulgaria.txt)                 | 🇨🇦 Canada                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Canada.txt)                 |
| 🇨🇱 Chile                  | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Chile.txt)                    | 🇨🇳 China                  | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/China.txt)                  |
| 🇨🇴 Colombia               | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Colombia.txt)                 | 🇨🇷 Costa Rica             | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Costa_Rica.txt)             |
| 🇭🇷 Croatia                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Croatia.txt)                  | 🇨🇾 Cyprus                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Cyprus.txt)                 |
| 🇨🇿 Czechia                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Czechia.txt)                  | 🇩🇰 Denmark                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Denmark.txt)                |
| 🇪🇨 Ecuador                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Ecuador.txt)                  | 🇪🇪 Estonia                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Estonia.txt)                |
| 🇫🇮 Finland                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Finland.txt)                  | 🇫🇷 France                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/France.txt)                 |
| 🇩🇪 Germany                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Germany.txt)                  | 🇬🇮 Gibraltar              | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Gibraltar.txt)              |
| 🇬🇷 Greece                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Greece.txt)                   | 🇬🇹 Guatemala              | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Guatemala.txt)              |
| 🇭🇰 Hong Kong              | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Hong_Kong.txt)                | 🇮🇸 Iceland                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Iceland.txt)                |
| 🇮🇳 India                  | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/India.txt)                    | 🇮🇩 Indonesia              | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Indonesia.txt)              |
| 🇮🇷 Iran                   | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Iran.txt)                     | 🇮🇪 Ireland                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Ireland.txt)                |
| 🇮🇱 Israel                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Israel.txt)                   | 🇮🇹 Italy                  | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Italy.txt)                  |
| 🇯🇵 Japan                  | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Japan.txt)                    | 🇯🇴 Jordan                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Jordan.txt)                 |
| 🇰🇿 Kazakhstan             | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Kazakhstan.txt)               | 🇰🇷 Korea Republic of      | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Korea_Republic_of.txt)      |
| 🇱🇻 Latvia                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Latvia.txt)                   | 🇱🇹 Lithuania              | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Lithuania.txt)              |
| 🇱🇺 Luxembourg             | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Luxembourg.txt)               | 🇲🇾 Malaysia               | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Malaysia.txt)               |
| 🇲🇹 Malta                  | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Malta.txt)                    | 🇲🇺 Mauritius              | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Mauritius.txt)              |
| 🇲🇽 Mexico                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Mexico.txt)                   | 🇲🇩 Moldova                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Moldova.txt)                |
| 🇲🇦 Morocco                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Morocco.txt)                  | 🇲🇲 Myanmar                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Myanmar.txt)                |
| 🇳🇱 Netherlands            | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Netherlands.txt)              | 🇳🇿 New Zealand            | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/New_Zealand.txt)            |
| 🇳🇬 Nigeria                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Nigeria.txt)                  | 🇲🇰 North Macedonia        | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/North_Macedonia.txt)        |
| 🇳🇴 Norway                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Norway.txt)                   | 🇻🇬 Virgin Islands British | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Virgin_Islands_British.txt) |
| 🇴🇲 Oman                   | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Oman.txt)                     | 🇵🇰 Pakistan               | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Pakistan.txt)               |
| 🇵🇾 Paraguay               | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Paraguay.txt)                 | 🇵🇪 Peru                   | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Peru.txt)                   |
| 🇵🇭 Philippines            | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Philippines.txt)              | 🇵🇱 Poland                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Poland.txt)                 |
| 🇵🇹 Portugal               | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Portugal.txt)                 | 🇵🇷 Puerto Rico            | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Puerto_Rico.txt)            |
| 🇷🇴 Romania                | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Romania.txt)                  | 🇷🇺 Russia                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Russia.txt)                 |
| 🇸🇦 Saudi Arabia           | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Saudi_Arabia.txt)             | 🇷🇸 Serbia                 | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Serbia.txt)                 |
| 🇸🇨 Seychelles             | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Seychelles.txt)               | 🇸🇬 Singapore              | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Singapore.txt)              |
| 🇸🇰 Slovakia               | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Slovakia.txt)                 | 🇸🇮 Slovenia               | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Slovenia.txt)               |
| 🇿🇦 South Africa           | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/South_Africa.txt)             | 🇪🇸 Spain                  | [Link](https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/main/category/Spain.txt)                  |
