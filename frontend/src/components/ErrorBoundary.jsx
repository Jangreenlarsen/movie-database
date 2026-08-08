import { Component } from "react";

// Safety net for uncaught render errors (CLAUDE.md regel 16 — en bruger må
// aldrig efterlades med en tavs/uforklaret fejl). Uden denne ville en
// uventet fejl blot blanke hele siden uden nogen vej tilbage undtagen at
// vide man skal genindlæse manuelt — set på iOS ved BUGS.md #35, hvor
// rodårsagen nu er rettet, men denne fanger alle fremtidige tilfælde af
// samme klasse fejl.
//
// Feature #89: bevidst ikke oversat. Denne komponent ligger uden om
// `I18nProvider` (main.jsx) — den skal netop kunne fange en fejl i selve
// App/provideren — så der er hverken en context at læse sproget fra eller
// en garanti for at brugerens indstillinger nåede at blive hentet. En
// hardkodet dansk besked er ærligere end at gætte sproget i det ene
// tilfælde hvor alt andet er gået galt.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Uventet fejl:", error, info?.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, textAlign: "center" }}>
          <h2>Der skete en uventet fejl</h2>
          <p className="muted">{this.state.error.message}</p>
          <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
            Genindlæs siden
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
