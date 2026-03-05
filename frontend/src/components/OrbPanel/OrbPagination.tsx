/** Pagination controls for orb panel sections. */

interface OrbPaginationProps {
  page: number
  count: number
  onPrev: () => void
  onNext: () => void
}

export function OrbPagination({
  page,
  count,
  onPrev,
  onNext,
}: OrbPaginationProps): React.ReactNode {
  if (count <= 1) return null
  return (
    <div className="orb-pagination">
      <button type="button" disabled={page === 0} onClick={onPrev}>
        ‹
      </button>
      <span>
        {page + 1}/{count}
      </span>
      <button type="button" disabled={page >= count - 1} onClick={onNext}>
        ›
      </button>
    </div>
  )
}
