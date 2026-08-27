(() => {
    const THEME_KEY = "mo-helpdesk-theme";
    const consoleEl = document.getElementById("console-output");
    const toastHost = document.getElementById("toast-host");

    function nowStamp() {
        return new Date().toLocaleTimeString("en-GB", { hour12: false });
    }

    function escapeHtml(text) {
        return String(text)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
    }

    function colorize(line) {
        let html = escapeHtml(line);
        html = html.replace(/^\[(.*?)\]/, '<span class="ts">[$1]</span>');
        html = html.replace(/\bGood\b/g, '<span class="ok-text">Good</span>');
        html = html.replace(/\bError\b/g, '<span class="err-text">Error</span>');
        html = html.replace(/\bFailed\b/g, '<span class="err-text">Failed</span>');
        return html;
    }

    function appendConsole(message, { error = false } = {}) {
        if (!consoleEl) return;
        const lines = String(message).split(/\r?\n/);
        const stamped = lines
            .map((line, index) => {
                const prefix = index === 0 ? `[${nowStamp()}] ` : "           ";
                const content = error && index === 0 ? `Error: ${line}` : line;
                return colorize(`${prefix}${content}`);
            })
            .join("\n");
        consoleEl.innerHTML += (consoleEl.innerHTML ? "\n" : "") + stamped;
        consoleEl.scrollTop = consoleEl.scrollHeight;
    }

    function toast(message) {
        if (!toastHost) return;
        const el = document.createElement("div");
        el.className = "toast";
        el.textContent = message;
        toastHost.appendChild(el);
        setTimeout(() => el.remove(), 2800);
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        const icon = document.getElementById("theme-icon");
        if (icon) {
            icon.className = theme === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
        }
        localStorage.setItem(THEME_KEY, theme);
    }

    function initTheme() {
        const saved = localStorage.getItem(THEME_KEY);
        applyTheme(saved === "dark" ? "dark" : "light");
        const toggle = document.getElementById("theme-toggle");
        if (toggle) {
            toggle.addEventListener("click", () => {
                const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
                applyTheme(next);
            });
        }
    }

    async function runTool(tool, button) {
        if (!tool) return;
        const confirmMsg = button?.dataset?.confirm;
        if (confirmMsg && !window.confirm(confirmMsg)) {
            appendConsole(`Cancelled ${tool.replaceAll("_", " ")}.`);
            return;
        }

        if (button) button.disabled = true;
        appendConsole(`Running ${tool.replaceAll("_", " ")}...`);

        try {
            const response = await fetch(`/api/system/tools/${tool}`, { method: "POST" });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.detail || "Tool failed");
            }
            if (data.output) {
                appendConsole(data.output);
            } else {
                appendConsole(`${tool.replaceAll("_", " ")} completed.`);
            }
            toast(`${tool.replaceAll("_", " ")} completed`);
        } catch (error) {
            appendConsole(error.message || "Request failed", { error: true });
            toast(error.message || "Request failed");
        } finally {
            if (button) button.disabled = false;
        }
    }

    function bindTools() {
        document.querySelectorAll("[data-tool]").forEach((button) => {
            button.addEventListener("click", () => runTool(button.dataset.tool, button));
        });
    }

    function bindSearch() {
        const input = document.getElementById("tool-search");
        if (!input) return;
        input.addEventListener("input", () => {
            const query = input.value.trim().toLowerCase();
            document.querySelectorAll(".qa-item").forEach((item) => {
                const hay = `${item.dataset.search || ""} ${item.textContent}`.toLowerCase();
                item.classList.toggle("hidden", Boolean(query) && !hay.includes(query));
            });
            document.querySelectorAll(".qa-card").forEach((card) => {
                const visible = [...card.querySelectorAll(".qa-item")].some((item) => !item.classList.contains("hidden"));
                card.classList.toggle("hidden", Boolean(query) && !visible);
            });
        });
    }

    function bindConsoleActions() {
        const clearBtn = document.getElementById("console-clear");
        const copyBtn = document.getElementById("console-copy");
        const saveBtn = document.getElementById("console-save");

        if (clearBtn && consoleEl) {
            clearBtn.addEventListener("click", () => {
                consoleEl.innerHTML = "";
                appendConsole("Console cleared.");
            });
        }

        if (copyBtn && consoleEl) {
            copyBtn.addEventListener("click", async () => {
                try {
                    await navigator.clipboard.writeText(consoleEl.innerText);
                    toast("Console copied");
                } catch {
                    toast("Copy failed");
                }
            });
        }

        if (saveBtn && consoleEl) {
            saveBtn.addEventListener("click", () => {
                const blob = new Blob([consoleEl.innerText], { type: "text/plain" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `helpdesk-console-${Date.now()}.txt`;
                a.click();
                URL.revokeObjectURL(url);
                toast("Console saved");
            });
        }
    }

    function updateHealth(health) {
        const card = document.getElementById("sidebar-health");
        const status = document.getElementById("health-status");
        const message = document.getElementById("health-message");
        const icon = document.getElementById("health-icon");
        if (!card || !health) return;
        card.dataset.level = health.level || "good";
        if (status) status.textContent = health.status;
        if (message) message.textContent = health.message;
        if (icon) {
            icon.className =
                health.level === "good"
                    ? "bi bi-check-circle-fill"
                    : health.level === "warning"
                      ? "bi bi-exclamation-triangle-fill"
                      : "bi bi-x-circle-fill";
        }
    }

    function updateStatusBar(data) {
        const last = document.getElementById("last-updated");
        const network = document.getElementById("network-status");
        const internet = document.getElementById("internet-status");
        if (last) last.textContent = data.last_updated;
        if (network) {
            network.textContent = data.network_connected ? "Connected" : "Disconnected";
            network.className = data.network_connected ? "ok" : "bad";
        }
        if (internet) {
            internet.textContent = data.internet_connected ? "Connected" : "Disconnected";
            internet.className = data.internet_connected ? "ok" : "bad";
        }
    }

    function updateInfoCards(data) {
        const map = {
            "info-computer": data.computer_name,
            "info-domain": data.domain,
            "info-user": data.logged_user,
            "info-os": data.os_name,
            "info-os-sub": data.os_subtitle,
            "info-cpu": data.cpu_name,
            "info-cpu-usage": `${Math.round(data.cpu_usage)}%`,
            "info-ram": `${data.ram_total} GB`,
            "info-ram-sub": `${data.ram_used} GB (${Math.round(data.ram_percent)}%) Used`,
            "info-disk": `${Math.round(data.disk_percent)}%`,
            "info-disk-sub": `${Math.round(data.disk_used)} GB / ${Math.round(data.disk_total)} GB Used`,
            "profile-name": data.logged_user,
        };
        Object.entries(map).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        });
        const cpuMeter = document.getElementById("cpu-meter");
        const ramMeter = document.getElementById("ram-meter");
        const diskMeter = document.getElementById("disk-meter");
        if (cpuMeter) {
            cpuMeter.style.width = `${data.cpu_usage}%`;
            cpuMeter.parentElement.classList.toggle("warn", data.cpu_usage >= 80);
        }
        if (ramMeter) ramMeter.style.width = `${data.ram_percent}%`;
        if (diskMeter) diskMeter.style.width = `${data.disk_percent}%`;
        updateHealth(data.health);
        updateStatusBar(data);
    }

    async function refreshSystem(seedConsole = false) {
        try {
            const response = await fetch("/api/system/info");
            if (!response.ok) throw new Error("Failed to refresh system info");
            const data = await response.json();
            updateInfoCards(data);
            if (seedConsole && consoleEl && !consoleEl.dataset.seeded) {
                consoleEl.dataset.seeded = "1";
                appendConsole(`System check started...`);
                appendConsole(`Computer: ${data.computer_name} (Domain: ${data.domain})`);
                appendConsole(`User: ${data.logged_user} | Session: Active`);
                appendConsole(`OS: ${data.os_name} — ${data.os_subtitle}`);
                appendConsole(`CPU: ${data.cpu_name} ${data.cpu_subtitle}`);
                appendConsole(`RAM: ${data.ram_used} GB / ${data.ram_total} GB (${Math.round(data.ram_percent)}%)`);
                appendConsole(`Disk C: ${Math.round(data.disk_used)} GB / ${Math.round(data.disk_total)} GB (${Math.round(data.disk_percent)}%)`);
                appendConsole(`System Health: ${data.health.status}`);
            }
        } catch (error) {
            if (seedConsole) appendConsole(error.message, { error: true });
        }
    }

    const customizeBtn = document.getElementById("customize-btn");
    if (customizeBtn) {
        customizeBtn.addEventListener("click", () => {
            toast("Customize: pin your favorite tools from each category");
            appendConsole("Customize panel: use Search tools to filter Quick Access items.");
        });
    }

    initTheme();
    bindTools();
    bindSearch();
    bindConsoleActions();

    if (document.getElementById("info-grid") || document.getElementById("console-output")) {
        refreshSystem(true);
        setInterval(() => refreshSystem(false), 2000);
    }

    window.moHelpdesk = { toast, appendConsole };
})();
