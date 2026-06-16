import { Modal, Button } from "dashboard";

const stage = {
  position: "relative" as const,
  width: 640,
  height: 360,
  background: "var(--color-bg-primary, #0a0a0b)",
  borderRadius: 8,
  overflow: "hidden",
};

/** Default — BuyModal-style: elevated surface, ESC chip header, Cancel + Confirm row. */
export function Default() {
  return (
    <div style={stage}>
      <Modal onClose={() => {}} maxWidth={400} ariaLabel="Buy AAPL">
        <Modal.Header onClose={() => {}}>
          <span className="font-mono font-bold" style={{ fontSize: 18, color: "var(--color-text-primary)" }}>
            Buy AAPL
          </span>
        </Modal.Header>
        <Modal.Body>
          <p style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
            10 shares at $192.50 = $1,925.00. Stop loss at -5%, take profit at +15%.
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" size="md" onClick={() => {}}>Cancel</Button>
          <Button variant="success" size="md" onClick={() => {}}>Buy 10 AAPL</Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}

/** Glass — CompanyInfoModal-style: blurred translucent surface, round ✕ close. */
export function Glass() {
  return (
    <div style={stage}>
      <Modal onClose={() => {}} variant="glass" maxWidth="28rem" ariaLabel="AAPL info">
        <button
          onClick={() => {}}
          className="absolute top-4 right-4 text-xs rounded-full w-6 h-6 flex items-center justify-center"
          style={{ color: "var(--color-text-secondary)", background: "rgba(255,255,255,0.06)" }}
          aria-label="Close"
        >
          ✕
        </button>
        <div style={{ paddingRight: 32 }}>
          <div className="font-mono font-bold" style={{ fontSize: 18, color: "var(--color-text-primary)" }}>AAPL</div>
          <div style={{ fontSize: 13, color: "var(--color-text-3)", marginTop: 4 }}>Apple Inc.</div>
          <p style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 12 }}>
            Designs, manufactures, and markets smartphones, personal computers,
            tablets, wearables, and accessories worldwide.
          </p>
        </div>
      </Modal>
    </div>
  );
}

/** Confirm — danger-action layout (Sell modal pattern). */
export function ConfirmDanger() {
  return (
    <div style={stage}>
      <Modal onClose={() => {}} maxWidth={380} ariaLabel="Sell AAPL">
        <Modal.Header onClose={() => {}}>
          <span className="font-mono font-bold" style={{ fontSize: 18, color: "var(--color-text-primary)" }}>
            Sell AAPL
          </span>
          <span className="font-mono text-xs font-semibold" style={{ color: "var(--color-profit)" }}>
            +12.4%
          </span>
        </Modal.Header>
        <Modal.Body>
          <p style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
            Closing 10 shares at market price. Realized P&L: +$215.40.
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" size="md" block onClick={() => {}}>Cancel</Button>
          <Button variant="danger" size="md" block onClick={() => {}}>Sell All AAPL</Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}
