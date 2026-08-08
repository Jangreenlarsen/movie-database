import { useT } from "../i18n";
import "./Login.css";

// Feature #66 — shown instead of the main app for a logged-in user whose
// account isn't yet `active`. Reuses Login.css's auth-screen/auth-card
// classes rather than inventing a parallel set of layout styles.
export default function PendingApproval({ user, onLogout }) {
  const t = useT();
  const isRejected = user.status === "rejected";

  return (
    <div className="auth-screen">
      <div className="card auth-card">
        <div className="auth-brand">
          <span className="brand-mark" aria-hidden="true">
            🎬
          </span>
          {t("app.brand")}
        </div>

        {isRejected ? (
          <div className="banner banner-error">
            {t("pending.rejected", { username: user.username })}
          </div>
        ) : (
          <div className="banner banner-info">
            {t("pending.waiting", { username: user.username })}
          </div>
        )}

        <button type="button" className="btn" onClick={onLogout}>
          {t("app.logout")}
        </button>
      </div>
    </div>
  );
}
