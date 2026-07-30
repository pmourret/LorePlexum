import { useEffect, useState } from 'react'

import type { SettingCheck } from '../api/client'
import { useSaveSettings, useSettings } from '../api/hooks'
import { Alert, ButtonSpinner, Loading, QueryError } from '../components/ui'

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

  if (settings.isPending) return <Loading label="Chargement des paramètres…" />
  if (settings.error) return <QueryError error={settings.error} />
  if (!settings.data) return null

  const { all_ok, checks, config_path } = settings.data

  // Nombre de réglages en défaut : « corrigez les champs en rouge » ne dit pas
  // combien il y en a, ni s'il faut faire défiler pour les trouver.
  const failing = checks.filter((check) => check.status === 'error').length
  // Modifications non enregistrées, pour prévenir avant de quitter la page.
  const dirty = checks.some((check) => (values[check.key] ?? '') !== check.value)

  return (
    <>
      <h1>Paramètres</h1>

      {save.isSuccess && !dirty && <Alert level="success">Paramètres enregistrés.</Alert>}
      {save.error && <QueryError error={save.error} />}

      {all_ok ? (
        <Alert level="success">Configuration valide — l'injection est prête.</Alert>
      ) : (
        <Alert level="warning">
          Configuration incomplète : {failing > 0 ? `${failing} réglage(s) en défaut` : 'des réglages sont vides'}
          . Les lignes concernées portent un liseré rouge ci-dessous.
        </Alert>
      )}

      <form
        className="card"
        aria-busy={save.isPending}
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

        <div className="submit-row">
          {/* Désactivé tant que rien n'a bougé : enregistrer à l'identique renvoyait
              « Paramètres enregistrés » sans que rien n'ait changé, ce qui laissait
              croire qu'une modification perdue avait été prise en compte. */}
          <button type="submit" className="btn primary" disabled={save.isPending || !dirty}>
            {save.isPending ? 'Enregistrement…' : 'Enregistrer'}
            {save.isPending && <ButtonSpinner />}
          </button>
          {dirty ? (
            <small className="unsaved">Modifications non enregistrées.</small>
          ) : (
            <small>Aucune modification à enregistrer.</small>
          )}
        </div>
      </form>

      <p className="muted settings-note">
        Les valeurs sont écrites dans <code>{config_path}</code>. La validation vérifie que
        les fichiers et dossiers existent réellement.
      </p>
      <p className="muted settings-note">
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
  const icon = check.status === 'ok' ? '✅' : check.status === 'error' ? '❌' : '—'
  const badge = dirty
    ? { className: 'empty', icon: '✎', text: 'Non enregistré' }
    : { className: check.status, icon, text: check.message }

  // Le message de statut décrit le champ : il faut le rattacher explicitement,
  // sinon la synthèse vocale lit le champ puis, plus tard et hors contexte, un
  // « fichier introuvable » orphelin.
  const statusId = `setting-status-${check.key}`

  return (
    <label className={`setting ${dirty ? '' : check.status}`}>
      <span className="setting-label">
        {check.label}
        {check.required && (
          <>
            <span className="req" aria-hidden="true"> *</span>
            <span className="sr-only"> (obligatoire)</span>
          </>
        )}
        <code>{check.key}</code>
      </span>
      <input
        type="text"
        value={value}
        // Signalé invalide seulement quand la valeur affichée est bien celle que le
        // serveur a refusée — pas pendant qu'on la corrige.
        aria-invalid={!dirty && check.status === 'error' ? true : undefined}
        aria-describedby={statusId}
        placeholder={check.kind ? 'chemin…' : 'valeur…'}
        spellCheck={false}
        autoComplete="off"
        onChange={(event) => onChange(event.target.value)}
      />
      <span className={`status-badge ${badge.className}`} id={statusId}>
        <span aria-hidden="true">{badge.icon}</span>
        {badge.text}
      </span>
    </label>
  )
}
