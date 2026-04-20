const API_BASE = (() => {
    const configured = window.GEO_TRUST_API_BASE;
    if (configured) return configured.replace(/\/$/, "");
    if (window.location.origin && window.location.origin !== "null") {
        return window.location.origin.replace(/\/$/, "");
    }
    return "http://111.229.115.101:8000";
})();

const SCAN_SESSION_PREFIX = "geo-trust-scan:";
const TILE_PROVIDERS = [
    {
        name: "Amap",
        url: "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
        options: {
            subdomains: ["1", "2", "3", "4"],
            maxZoom: 18,
            attribution: "Amap"
        }
    },
    {
        name: "OpenStreetMap",
        url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        options: {
            maxZoom: 19,
            attribution: "OpenStreetMap"
        }
    }
];

let leafletMap = null;

function getTokenFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const queryToken = urlParams.get("token");
    if (queryToken) return queryToken;

    const pathMatch = window.location.pathname.match(/\/trace\/([^/?#]+)/);
    if (pathMatch && pathMatch[1]) return decodeURIComponent(pathMatch[1]);
    return null;
}

function buildTraceUrl(token) {
    return `${API_BASE}/api/trace/${encodeURIComponent(token)}`;
}

function buildScanUrl(token) {
    return `${API_BASE}/api/scan/${encodeURIComponent(token)}`;
}

function normalizeImages(raw) {
    const uploadedGallery = (raw.gallery_images || [])
        .map((item, index) => ({
            title: item.title || `Supporting Image ${index + 1}`,
            image: item.image || item.image_url || ""
        }))
        .filter((item) => item.image);

    if (uploadedGallery.length > 0) return uploadedGallery;

    return (raw.cert_images || [])
        .map((item, index) => ({
            title: item.title || `Supporting Image ${index + 1}`,
            image: item.image || item.image_url || (typeof item === "string" ? item : "")
        }))
        .filter((item) => item.image);
}

async function fetchTraceData(token) {
    const response = await fetch(buildTraceUrl(token), {
        headers: { Accept: "application/json" }
    });
    if (!response.ok) throw new Error(`trace request failed: ${response.status}`);

    const raw = await response.json();
    return {
        ...raw,
        display_images: normalizeImages(raw)
    };
}

async function postScanRecord(token, scanData) {
    const response = await fetch(buildScanUrl(token), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(scanData)
    });
    if (!response.ok) throw new Error(`scan request failed: ${response.status}`);
    return response.json();
}

async function reportScanEvent(token) {
    const sessionKey = `${SCAN_SESSION_PREFIX}${token}`;
    if (sessionStorage.getItem(sessionKey) === "reported") return;

    const now = new Date();
    const scanData = {
        scan_time: now.toISOString().slice(0, 19),
        device_info: navigator.userAgent,
        scan_lng: null,
        scan_lat: null
    };

    const markReported = () => sessionStorage.setItem(sessionKey, "reported");

    if (!("geolocation" in navigator)) {
        await postScanRecord(token, scanData);
        markReported();
        return;
    }

    await new Promise((resolve) => {
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                scanData.scan_lng = position.coords.longitude;
                scanData.scan_lat = position.coords.latitude;
                scanData.scan_accuracy = position.coords.accuracy;
                try {
                    await postScanRecord(token, scanData);
                    markReported();
                } finally {
                    resolve();
                }
            },
            async () => {
                try {
                    await postScanRecord(token, scanData);
                    markReported();
                } finally {
                    resolve();
                }
            },
            { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
        );
    });
}

function getRiskLevelLabel(level) {
    if (level === "none") return "正常";
    if (level === "low") return "低";
    if (level === "medium") return "需关注";
    if (level === "high") return "异常";
    return "未知";
}

function updateStatusUI(data) {
    const banner = document.getElementById("status-banner");
    const statusText = document.getElementById("status-text");
    const riskText = document.getElementById("risk-text");
    const riskLevelText = document.getElementById("risk-level-text");
    const statusBadge = document.getElementById("status-badge");
    const alertPill = document.getElementById("alert-pill");
    const scanTag = document.getElementById("scan-tag");

    banner.className = "alert-banner";
    statusBadge.className = "badge";

    if (data.status === "normal") {
        banner.classList.add("normal");
        statusText.textContent = "登记信息正常";
        riskText.textContent = "该产品已由安卓端完成登记，当前未发现异常扫码行为。";
        statusBadge.classList.add("badge-green");
        statusBadge.textContent = "正常";
        alertPill.textContent = "可信";
    } else if (data.status === "opened") {
        banner.classList.add("opened");
        statusText.textContent = "已开封";
        riskText.textContent = "该溯源码已被查看，请结合包装状态确认是否为首次开启。";
        statusBadge.classList.add("badge-warning");
        statusBadge.textContent = "已开封";
        alertPill.textContent = "已扫码";
    } else if (data.status === "risky") {
        banner.classList.add("risky");
        statusText.textContent = "检测到异常扫码";
        riskText.textContent = "系统检测到异常流转或疑似异常扫码行为，请结合时间地点继续核验。";
        statusBadge.classList.add("badge-danger");
        statusBadge.textContent = "预警";
        alertPill.textContent = "风险";
    } else {
        banner.classList.add("opened");
        statusText.textContent = "状态待判断";
        riskText.textContent = "该产品已登记，但系统暂未形成完整判断。";
        statusBadge.classList.add("badge-warning");
        statusBadge.textContent = "待判断";
        alertPill.textContent = "待判断";
    }

    const level = data.risk_level || "none";
    scanTag.textContent = `累计扫码 ${data.scan_count || 0} 次`;
    riskLevelText.textContent = `扫码状态：${getRiskLevelLabel(level)}`;
    riskLevelText.className = `risk-level-text risk-level-${level === "none" ? "none" : level}`;
}

function addTileLayer(map, fallbackElement, providerIndex = 0) {
    if (providerIndex >= TILE_PROVIDERS.length) {
        fallbackElement.style.display = "";
        fallbackElement.textContent = "所有地图底图均加载失败。";
        return;
    }

    const provider = TILE_PROVIDERS[providerIndex];
    const layer = L.tileLayer(provider.url, provider.options);
    let switched = false;

    layer.on("tileerror", () => {
        if (switched) return;
        switched = true;
        map.removeLayer(layer);
        addTileLayer(map, fallbackElement, providerIndex + 1);
    });

    layer.on("load", () => {
        fallbackElement.style.display = "none";
    });

    layer.addTo(map);
}

function renderMap(data) {
    const mapElement = document.getElementById("map");
    const fallbackElement = document.getElementById("map-fallback");
    const lat = Number(data.map_lat ?? data.origin_lat);
    const lng = Number(data.map_lng ?? data.origin_lng);

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
        mapElement.style.display = "none";
        fallbackElement.style.display = "";
        fallbackElement.textContent = "当前产品没有可用于展示的有效坐标。";
        return;
    }

    if (typeof window.L === "undefined") {
        mapElement.style.display = "none";
        fallbackElement.style.display = "";
        fallbackElement.textContent = `地图组件加载失败，登记坐标为 ${lng.toFixed(6)}, ${lat.toFixed(6)}。`;
        return;
    }

    fallbackElement.style.display = "none";
    mapElement.style.display = "";

    if (leafletMap) leafletMap.remove();
    leafletMap = L.map("map", { zoomControl: true }).setView([lat, lng], 13);
    addTileLayer(leafletMap, fallbackElement);

    const markerIcon = L.divIcon({
        className: "geo-marker",
        html: '<span class="geo-marker-dot"></span>',
        iconSize: [22, 22],
        iconAnchor: [11, 11]
    });

    L.marker([lat, lng], { icon: markerIcon }).addTo(leafletMap)
        .bindPopup(`<b>${data.region_name || "登记产区"}</b><br>登记坐标点`)
        .openPopup();

    window.setTimeout(() => {
        leafletMap.invalidateSize();
    }, 200);
}

function renderGallery(images) {
    const container = document.getElementById("gallery-grid");
    container.innerHTML = "";

    if (!images.length) {
        document.getElementById("gallery-empty").style.display = "";
        return;
    }

    document.getElementById("gallery-empty").style.display = "none";
    images.forEach((item) => {
        const card = document.createElement("div");
        card.className = "media-image-card";
        card.innerHTML = `
            <img src="${item.image}" alt="${item.title}">
            <p>${item.title}</p>
        `;
        const img = card.querySelector("img");
        img.addEventListener("click", () => openImagePreview(item.image, item.title));
        container.appendChild(card);
    });
}

function renderPage(data) {
    document.getElementById("hero-product-name").textContent = data.product_name || "-";
    document.getElementById("product-code").textContent = data.product_code || "-";
    document.getElementById("batch-no").textContent = data.batch_no || "-";
    document.getElementById("producer-name").textContent = data.producer_name || "-";
    document.getElementById("region-name").textContent = data.region_name || "-";
    document.getElementById("origin-time").textContent = data.origin_fix_time || "-";
    document.getElementById("scan-count").textContent = data.scan_count ?? 0;
    document.getElementById("first-scan-time").textContent = data.first_scan_time || "暂无扫码记录";
    document.getElementById("last-scan-time").textContent = data.last_scan_time || "暂无扫码记录";
    document.getElementById("map-region-name").textContent = data.region_name || "-";

    const productImage = document.getElementById("alert-product-image");
    if (data.product_image) {
        productImage.src = data.product_image;
        productImage.style.visibility = "visible";
    } else {
        productImage.removeAttribute("src");
        productImage.style.visibility = "hidden";
    }

    updateStatusUI(data);
    renderMap(data);
    renderGallery(data.display_images || []);
}

function openImagePreview(src, title) {
    const modal = document.getElementById("image-preview-modal");
    document.getElementById("image-preview-img").src = src;
    document.getElementById("image-preview-title").textContent = title || "图片预览";
    modal.classList.add("show");
}

function bindModalEvents() {
    document.getElementById("image-preview-close").onclick = () => {
        document.getElementById("image-preview-modal").classList.remove("show");
    };
    document.getElementById("image-preview-backdrop").onclick = () => {
        document.getElementById("image-preview-modal").classList.remove("show");
    };
}

async function init() {
    const activeToken = getTokenFromUrl();
    if (!activeToken) {
        document.getElementById("status-text").textContent = "缺少溯源码";
        document.getElementById("risk-text").textContent = "请通过完整溯源链接或二维码打开当前页面。";
        return;
    }

    try {
        const data = await fetchTraceData(activeToken);
        renderPage(data);
        bindModalEvents();
        await reportScanEvent(activeToken);
    } catch (error) {
        console.error(error);
        document.getElementById("status-text").textContent = "溯源数据加载失败";
        document.getElementById("risk-text").textContent = "请确认二维码有效，并确认后端服务正在运行。";
    }
}

init();
