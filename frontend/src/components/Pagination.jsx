import { useT } from "../i18n";

const PAGE_SIZE_OPTIONS = [24, 48, 96, 200];

export default function Pagination({ page, pageSize, total, onPageChange, onPageSizeChange }) {
  const t = useT();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="pagination">
      <label className="pagination-size">
        {t("pagination.perPage")}
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
        >
          {PAGE_SIZE_OPTIONS.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </label>

      <div className="pagination-nav">
        <button
          type="button"
          className="btn"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          {t("pagination.previous")}
        </button>
        <span className="muted">
          {t("pagination.status", { page, totalPages, total })}
        </span>
        <button
          type="button"
          className="btn"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
        >
          {t("pagination.next")}
        </button>
      </div>
    </div>
  );
}
