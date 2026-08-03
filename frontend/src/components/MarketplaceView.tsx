import { Search, Star, Store } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { MarketplaceItem } from "../types";

const CATEGORIES = ["All", "Documents", "Images", "Developer", "Research"];

export function MarketplaceView() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [tab, setTab] = useState<"featured" | "installed" | "updates">("featured");
  const [catalog, setCatalog] = useState<MarketplaceItem[]>([]);
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const packs = await api.listPacks();
      setCatalog(packs);
    } catch {
      setNotice("Could not load Creator Packs from API.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const items = useMemo(() => {
    let list = [...catalog];
    if (tab === "installed") list = list.filter((i) => i.installed);
    if (tab === "updates") list = list.filter((i) => i.hasUpdate);
    if (tab === "featured") list = list.filter((i) => i.featured);
    if (category !== "All") list = list.filter((i) => i.category === category);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (i) =>
          i.name.toLowerCase().includes(q) ||
          i.description.toLowerCase().includes(q) ||
          i.developer.toLowerCase().includes(q)
      );
    }
    return list;
  }, [search, category, tab, catalog]);

  const onInstall = async (item: MarketplaceItem) => {
    if (item.installed || installingId) return;
    setInstallingId(item.id);
    setNotice(null);
    try {
      const res = await api.installPack(item.id);
      setCatalog((prev) => prev.map((p) => (p.id === item.id ? { ...p, ...res.pack } : p)));
      const caps = (res.pack.capabilities || []).join(", ");
      setNotice(`Installed "${res.pack.name}" — registered capabilities: ${caps || "none"}`);
    } catch {
      setNotice(`Failed to install ${item.name}`);
    } finally {
      setInstallingId(null);
    }
  };

  return (
    <div className="dashboard-view marketplace-view">
      <header className="dashboard-header">
        <div>
          <h1>
            <Store size={22} /> Marketplace
          </h1>
          <p className="marketplace-preview-badge">
            Creator Packs — install registers capabilities with the Capability Registry
          </p>
        </div>
      </header>

      {notice && <p className="marketplace-notice">{notice}</p>}
      {loading && <p className="marketplace-notice">Loading packs…</p>}

      <div className="marketplace-tabs">
        {(["featured", "installed", "updates"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={tab === t ? "pill active" : "pill"}
            onClick={() => setTab(t)}
          >
            {t === "featured" ? "Featured" : t === "installed" ? "Installed" : "Updates"}
          </button>
        ))}
      </div>

      <div className="file-manager-toolbar">
        <div className="search-field">
          <Search size={16} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search packs…"
          />
        </div>
        <div className="filter-pills">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              className={category === c ? "pill active" : "pill"}
              onClick={() => setCategory(c)}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="marketplace-grid">
        {items.map((item) => (
          <article key={item.id} className="marketplace-card glass-panel">
            <div className="marketplace-card-icon">{item.name.slice(0, 1)}</div>
            <div className="marketplace-card-body">
              <h3>{item.name}</h3>
              <span className="marketplace-dev">
                {item.developer} · v{item.version}
              </span>
              <p>{item.description}</p>
              <div className="marketplace-meta">
                <span>
                  <Star size={14} /> {item.rating}
                </span>
                <span>{item.installs.toLocaleString()} installs</span>
                <span className="chip">{item.category}</span>
              </div>
            </div>
            <div className="marketplace-card-actions">
              <button
                type="button"
                className="btn-primary-sm"
                disabled={installingId === item.id || !!item.installed}
                title={item.installed ? "Installed" : "Install pack"}
                onClick={() => void onInstall(item)}
              >
                {item.installed
                  ? "Installed"
                  : installingId === item.id
                    ? "Installing…"
                    : "Install"}
              </button>
              <button type="button" className="btn-ghost" disabled>
                Details
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
