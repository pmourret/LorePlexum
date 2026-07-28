import type { CalendarData, GameDate } from '../api/client'

/**
 * Sélecteur de date du calendrier tamrielien.
 *
 * Tout est calculé **localement** à partir de `GET /api/v1/calendar`, qui renvoie
 * les douze mois avec leur nombre de jours. L'ancienne interface faisait deux
 * allers-retours HTMX pour ça — `/suggest-date` au changement de catégorie et
 * `/date-days` au changement de mois, juste pour rebâtir le menu « jour ».
 */
export default function DateField({
  calendar,
  value,
  onChange,
}: {
  calendar: CalendarData
  value: GameDate
  onChange: (date: GameDate) => void
}) {
  const month = calendar.months[value.month_index] ?? calendar.months[0]
  const maxDay = month.days

  function set(changes: Partial<GameDate>) {
    const next = { ...value, ...changes }
    // Changer de mois pour un mois plus court ramène le jour au dernier valide
    // (31 en Sun's Dawn -> 28) plutôt que de laisser une date impossible.
    const days = calendar.months[next.month_index]?.days ?? 31
    next.day = Math.max(1, Math.min(next.day, days))
    onChange(next)
  }

  return (
    <div className="date-block">
      <span className="date-legend">Date de la session (calendrier tamrielien)</span>
      <div className="date-grid">
        <label>
          Mois
          <select
            value={value.month_index}
            onChange={(event) => set({ month_index: Number(event.target.value) })}
          >
            {calendar.months.map((m) => (
              <option key={m.index} value={m.index}>
                {m.name_en}
              </option>
            ))}
          </select>
        </label>
        <label>
          Jour
          <select value={value.day} onChange={(event) => set({ day: Number(event.target.value) })}>
            {Array.from({ length: maxDay }, (_, i) => i + 1).map((day) => (
              <option key={day} value={day}>
                {day}
              </option>
            ))}
          </select>
        </label>
        <label>
          Ère
          <select value={value.era} onChange={(event) => set({ era: Number(event.target.value) })}>
            {calendar.eras.map((era) => (
              <option key={era} value={era}>
                {era}E
              </option>
            ))}
          </select>
        </label>
        <label>
          Année
          <input
            type="number"
            min={1}
            value={value.year}
            onChange={(event) => set({ year: Math.max(1, Number(event.target.value) || 1) })}
          />
        </label>
      </div>
      <small>
        Ex. « {month.name_en}, {value.day}, {value.era}E {value.year} » — {month.name_fr},{' '}
        {maxDay} jours. Pré-remplie avec la dernière date connue de la catégorie ; modifiable.
      </small>
    </div>
  )
}
