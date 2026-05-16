import type { DailyMatchCount } from '../lib/stats'

const CHART_HEIGHT = 160
const BAR_GAP = 4

function formatDayLabel(isoDate: string): string {
  const d = new Date(`${isoDate}T12:00:00`)
  return d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' })
}

function formatDayTitle(isoDate: string): string {
  const d = new Date(`${isoDate}T12:00:00`)
  return d.toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function DailyMatchesChart({ days }: { days: DailyMatchCount[] }) {
  const maxCount = Math.max(1, ...days.map((d) => d.count))
  const barCount = days.length
  const barWidth =
    barCount > 0
      ? `calc((100% - ${(barCount - 1) * BAR_GAP}px) / ${barCount})`
      : '0px'

  return (
    <div className="space-y-3">
      <div
        className="flex items-end gap-1"
        style={{ height: CHART_HEIGHT }}
        role="img"
        aria-label="Daily matches bar chart for the last two weeks"
      >
        {days.map((day) => {
          const heightPct = day.count === 0 ? 0 : (day.count / maxCount) * 100
          return (
            <div
              key={day.date}
              className="group flex min-w-0 flex-1 flex-col items-center justify-end"
              style={{ maxWidth: barWidth }}
            >
              <span
                className="mb-1 hidden text-[10px] font-medium text-zinc-600 group-hover:block sm:block"
                title={`${day.count} match${day.count === 1 ? '' : 'es'}`}
              >
                {day.count > 0 ? day.count : ''}
              </span>
              <div
                className="w-full min-h-[2px] rounded-t transition-[height] group-hover:bg-indigo-600"
                style={{
                  height: day.count === 0 ? '2px' : `${heightPct}%`,
                  backgroundColor: day.count === 0 ? '#e4e4e7' : '#4f46e5',
                }}
                title={`${formatDayTitle(day.date)}: ${day.count} match${day.count === 1 ? '' : 'es'}`}
              />
            </div>
          )
        })}
      </div>
      <div className="flex gap-1 text-[10px] text-zinc-400">
        {days.map((day, i) => (
          <span
            key={day.date}
            className="min-w-0 flex-1 truncate text-center"
            title={formatDayTitle(day.date)}
          >
            {i === 0 || i === days.length - 1 || i === Math.floor(days.length / 2)
              ? formatDayLabel(day.date)
              : ''}
          </span>
        ))}
      </div>
    </div>
  )
}
