import "./Login.css";

// Feature #66 — shown instead of the main app for a logged-in user whose
// account isn't yet `active`. Reuses Login.css's auth-screen/auth-card
// classes rather than inventing a parallel set of layout styles.
export default function PendingApproval({ user, onLogout }) {
  const isRejected = user.status === "rejected";

  return (
    <div className="auth-screen">
      <div className="card auth-card">
        <div className="auth-brand">
          <span className="brand-mark" aria-hidden="true">
            🎬
          </span>
          Film &amp; TV-bibliotek
        </div>

        {isRejected ? (
          <div className="banner banner-error">
            Din konto ({user.username}) er blevet afvist. Kontakt en administrator hvis du mener
            det er en fejl.
          </div>
        ) : (
          <div className="banner banner-info">
            Din konto ({user.username}) afventer godkendelse fra en administrator. Prøv igen
            senere, eller kontakt en administrator.
          </div>
        )}

        <button type="button" className="btn" onClick={onLogout}>
          Log ud
        </button>
      </div>
    </div>
  );
}
