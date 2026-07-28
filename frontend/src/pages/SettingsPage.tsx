import { useEffect, useState } from 'react'

import type { SettingCheck } from '../api/client'
import { useSaveSettings, useSettings } from '../api/hooks'
import { Alert, Loading, QueryError } from '../components/ui'

export default function SettingsPage() {
  const settings = useSettings()
  const save = useSaveSettings()

  // Formulaire non contrôlé par le serveur : on part des valeurs reçues, puis
  // l'utilisateur édite librement jusqu'à l'enregistrement.
  const [values, setValues] = useState<Record<string, string>>({})

  useEffect(() => {
    if (settings.data) {
      setValues(Object.fromEntries(settings.data.checks.map((c) => [c.key, c.value])))
    }
  }, [settings.data])

  if (settings.isPending) return <Loading />
  if (settings.error) return <QueryError error={settings.error} />
  if (!settings.data) return null

  const { all_ok, checks, config_path } = settings.data

  return (
    <>
      <h1>Paramètres</h1>

      {save.isSuccess && <Alert level="success">Paramètres enregistrés.</Alert>}
      {save.error && <QueryError error={save.error} />}

      {all_ok ? (
        <Alert level="success">Configuration valide — l'injection est prête.</Alert>
      ) : (
        <Alert level="warning">
          Configuration incomplète : corrigez les champs en rouge ci-dessous.
        </Alert>
      )}

      <form
        className="card"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(values)
        }}
      >
        {checks.map((check) => (
          <SettingField
            key={check.key}
            check={check}
            value={values[check.key] ?? ''}
            onChange={(value) => setValues((previous) => ({ ...previous, [check.key]: value }))}
          />
        ))}

        <button type="submit" className="btn primary" disabled={save.isPending}>
          Enregistrer
          {save.isPending && <span className="spinner" />}
        </button>
      </form>

      <p className="muted">
        Les valeurs sont écrites dans <code>{config_path}</code>. La validation vérifie que
        les fichiers et dossiers existent réellement.
      </p>
      <p className="muted">
        Une variable d'environnement de même nom reste prioritaire sur la valeur écrite ici —
        c'est ainsi que la configuration arrive en conteneur.
      </p>
    </>
  )
}

function SettingField({
  check,
  value,
  onChange,
}: {
  check: SettingCheck
  value: string
  onChange: (value: string) => void
}) {
  // Le statut affiché est celui de la dernière validation serveur ; il ne suit pas
  // la frappe. Une valeur modifiée mais non enregistrée n'a pas encore été vérifiée.
  const dirty = value !== check.value
  const badge = dirty
    ? { className: 'empty', text: '— Non enregistré' }
    : {
        className: check.status,
        text: `${check.status === 'ok' ? '✅' : check.status === 'error' ? '❌' : '—'} ${check.message}`,
      }

  return (
    <label className={`setting ${dirty ? '' : check.status}`}>
      <span className="setting-label">
        {check.label}
        {check.required && <span className="req"> *</span>}
        <code>{check.key}</code>
      </span>
      <input
        type="text"
        value={value}
        placeholder={check.kind ? 'chemin…' : 'valeur…'}
        onChange={(event) => onChange(event.target.value)}
      />
      <span className={`status-badge ${badge.className}`}>{badge.text}</span>
    </label>
  )
}
