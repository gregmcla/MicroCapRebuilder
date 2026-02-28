/** Collapsible sidebar — portfolio list + nav tabs + status. */

import { useUIStore, usePortfolioStore } from "../lib/store";
import { usePortfolios } from "../hooks/usePortfolios";
import type { RightTab } from "../lib/store";

// ── Icon components (inline SVG) ──────────────────────────────────────────────

function IconSummary({ className }: { className?: string }) {
  return (
    <svg className={className} width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25" />
      <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25" />
      <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25" />
      <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  );
}

function IconRisk({ className }: { className?: string }) {
  return (
    <svg className={className} width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M8 1.5L14 13H2L8 1.5Z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
      <line x1="8" y1="6" x2="8" y2="9.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
      <circle cx="8" cy="11.5" r="0.75" fill="currentColor" />
    </svg>
  );
}

function IconPerformance({ className }: { className?: string }) {
  return (
    <svg className={className} width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polyline points="1,12 5,7 9,9.5 14,3" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
      <polyline points="11,3 14,3 14,6" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconPortfolio({ className }: { className?: string }) {
  return (
    <svg className={className} width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="4" width="12" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
      <path d="M4.5 4V3a2.5 2.5 0 0 1 5 0v1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function IconChevronLeft({ className }: { className?: string }) {
  return (
    <svg className={className} width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polyline points="10,4 6,8 10,12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconChevronRight({ className }: { className?: string }) {
  return (
    <svg className={className} width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polyline points="6,4 10,8 6,12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Nav item config ────────────────────────────────────────────────────────────

interface NavItem {
  tab: RightTab;
  label: string;
  Icon: React.FC<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { tab: "summary",     label: "Summary",     Icon: IconSummary },
  { tab: "risk",        label: "Risk",        Icon: IconRisk },
  { tab: "performance", label: "Performance", Icon: IconPerformance },
];

// ── Sidebar ────────────────────────────────────────────────────────────────────

export default function Sidebar() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const rightTab = useUIStore((s) => s.rightTab);
  const setRightTab = useUIStore((s) => s.setRightTab);
  const activePortfolioId = usePortfolioStore((s) => s.activePortfolioId);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const { data: portfolioList } = usePortfolios();

  const portfolios = portfolioList?.portfolios ?? [];

  return (
    <aside
      style={{
        width: collapsed ? "48px" : "232px",
        transition: "width 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
        flexShrink: 0,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid var(--border-0)",
        background: "var(--surface-0)",
      }}
    >
      {/* ── Portfolio section ──────────────────────────────────────────────── */}
      <div className="flex flex-col pt-3 pb-2">
        {!collapsed && (
          <span
            style={{
              fontSize: "9px",
              fontWeight: 600,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--text-0)",
              padding: "0 12px",
              marginBottom: "4px",
            }}
          >
            Portfolios
          </span>
        )}

        {/* Overview entry */}
        <PortfolioRow
          id="overview"
          label="Overview"
          active={activePortfolioId === "overview"}
          collapsed={collapsed}
          onClick={() => setPortfolio("overview")}
        />

        {portfolios.map((p) => (
          <PortfolioRow
            key={p.id}
            id={p.id}
            label={p.name}
            active={activePortfolioId === p.id}
            collapsed={collapsed}
            onClick={() => setPortfolio(p.id)}
          />
        ))}
      </div>

      {/* ── Divider ────────────────────────────────────────────────────────── */}
      <div style={{ height: "1px", background: "var(--border-0)", margin: "4px 0" }} />

      {/* ── Nav section ────────────────────────────────────────────────────── */}
      <div className="flex flex-col py-2">
        {!collapsed && (
          <span
            style={{
              fontSize: "9px",
              fontWeight: 600,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--text-0)",
              padding: "0 12px",
              marginBottom: "4px",
            }}
          >
            View
          </span>
        )}

        {NAV_ITEMS.map(({ tab, label, Icon }) => {
          const isActive = rightTab === tab;
          return (
            <NavRow
              key={tab}
              label={label}
              active={isActive}
              collapsed={collapsed}
              Icon={Icon}
              onClick={() => setRightTab(tab)}
            />
          );
        })}
      </div>

      {/* ── Spacer ─────────────────────────────────────────────────────────── */}
      <div style={{ flex: 1 }} />

      {/* ── Status section (expanded only) ─────────────────────────────────── */}
      {!collapsed && (
        <div
          style={{
            padding: "8px 12px",
            borderTop: "1px solid var(--border-0)",
          }}
        >
          <div
            style={{
              fontSize: "9px",
              fontWeight: 600,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--text-0)",
              marginBottom: "4px",
            }}
          >
            Status
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                background: "var(--green)",
                flexShrink: 0,
                display: "inline-block",
              }}
            />
            <span style={{ fontSize: "10px", color: "var(--text-1)" }}>Paper mode</span>
          </div>
        </div>
      )}

      {/* ── Collapse toggle ─────────────────────────────────────────────────── */}
      <button
        onClick={toggleSidebar}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "40px",
          borderTop: "1px solid var(--border-0)",
          background: "transparent",
          cursor: "pointer",
          color: "var(--text-1)",
          transition: "color 0.15s",
          flexShrink: 0,
          width: "100%",
          outline: "none",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-3)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-1)";
        }}
      >
        {collapsed ? <IconChevronRight /> : <IconChevronLeft />}
      </button>
    </aside>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function PortfolioRow({
  label,
  active,
  collapsed,
  onClick,
}: {
  id?: string;
  label: string;
  active: boolean;
  collapsed: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={collapsed ? label : undefined}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: collapsed ? "7px 0" : "7px 12px",
        justifyContent: collapsed ? "center" : "flex-start",
        width: "100%",
        background: active ? "rgba(124,92,252,0.06)" : "transparent",
        border: "none",
        borderLeft: active ? "3px solid var(--accent)" : "3px solid transparent",
        cursor: "pointer",
        color: active ? "var(--text-3)" : "var(--text-1)",
        transition: "background 0.15s, color 0.15s",
        textAlign: "left",
        minWidth: 0,
      }}
      onMouseEnter={(e) => {
        if (!active) {
          (e.currentTarget as HTMLButtonElement).style.background =
            "rgba(255,255,255,0.03)";
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          (e.currentTarget as HTMLButtonElement).style.background = "transparent";
        }
      }}
    >
      <IconPortfolio
        className=""
        /* opacity handled inline */
      />
      {!collapsed && (
        <span
          style={{
            fontSize: "12px",
            fontWeight: active ? 500 : 400,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            minWidth: 0,
          }}
        >
          {label}
        </span>
      )}
    </button>
  );
}

function NavRow({
  label,
  active,
  collapsed,
  Icon,
  onClick,
}: {
  label: string;
  active: boolean;
  collapsed: boolean;
  Icon: React.FC<{ className?: string }>;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={collapsed ? label : undefined}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: collapsed ? "8px 0" : "8px 12px",
        justifyContent: collapsed ? "center" : "flex-start",
        width: "100%",
        background: active ? "rgba(124,92,252,0.06)" : "transparent",
        border: "none",
        borderLeft: active ? "3px solid var(--accent)" : "3px solid transparent",
        cursor: "pointer",
        color: active ? "var(--text-3)" : "var(--text-1)",
        transition: "background 0.15s, color 0.15s",
        textAlign: "left",
        minWidth: 0,
      }}
      onMouseEnter={(e) => {
        if (!active) {
          (e.currentTarget as HTMLButtonElement).style.background =
            "rgba(255,255,255,0.03)";
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          (e.currentTarget as HTMLButtonElement).style.background = "transparent";
        }
      }}
    >
      <Icon
        className=""
        /* color inherited from button */
      />
      {!collapsed && (
        <span
          style={{
            fontSize: "12px",
            fontWeight: active ? 500 : 400,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            minWidth: 0,
          }}
        >
          {label}
        </span>
      )}
    </button>
  );
}
