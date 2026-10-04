# Techem Mieterportal für Home Assistant

Version 0.2.0 – erste Testversion. Getestet gegen Home Assistant Core 2026.9.4. Mindestversion dieses Pakets: 2026.9.0. Inoffizielle Integration, nicht von Techem herausgegeben.

## Installation für den ersten Test

1. ZIP entpacken.
2. Den Ordner `custom_components/techem_portal` in das Home-Assistant-Konfigurationsverzeichnis kopieren. Ergebnis: `/config/custom_components/techem_portal/manifest.json`. Falls `custom_components` bereits existiert, nur den Unterordner `techem_portal` ergänzen.
3. Home Assistant vollständig neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Techem Mieterportal** öffnen.
5. E-Mail, Passwort und Abruftag eingeben. Bei mehreren Verbrauchsstellen eine auswählen.

Es wird ein Eintrag pro Konto unterstützt, mit einer ausgewählten Verbrauchsstelle. Mehrere unterschiedliche Konten können separat eingerichtet werden. Im Einrichtungsdialog werden die Zugangsdaten gegen Techem geprüft.

## Entitäten

Unter dem Gerät mit der Adresse stehen:

- **Heizverbrauch** in kWh.
- **Heizverbrauch Originaleinheiten**, bei HCU als „Einheiten“.
- **Verbrauchsstelle**: Straße als Zustand; Straße, PLZ, Ort und Geschoss als Attribute (`street`, `zip`, `city`, `floor`).
- **Letzter erfolgreicher Abruf**.
- **Abrufstatus**: Wartet, Erfolgreich, Erneuter Versuch ausstehend oder Anmeldung erforderlich.
- **Jetzt abrufen** als Button.

Die Verbrauchssensoren haben die Attribute `consumption_month`, `target_month`, `fetch_status`, `last_successful_fetch`, `source_status` und `source_revision`. `consumption_month` bezeichnet stets den tatsächlich importierten Monat.

## Zeitplanung

- Beim ersten Start wird einmalig der Vormonat abgefragt, unabhängig vom eingestellten Abruftag.
- Danach wird stündlich lokal geprüft, ob ein Abruf fällig ist. Dabei entsteht noch keine Anfrage an Techem.
- Ab dem Abruftag wird der Vormonat einmal erfolgreich importiert. Beispiel: am 5. Oktober wird September abgefragt.
- Bei einem Abruftag 29–31 gilt in kürzeren Monaten der letzte Monatstag.
- Es gilt die in Home Assistant eingestellte Zeitzone. Es gibt keine minutengenaue feste Abrufuhrzeit; der Abruf erfolgt beim nächsten stündlichen Prüflauf.
- War Home Assistant ausgeschaltet, wird ein fälliger Abruf nach dem Start nachgeholt.
- Fehlende oder nicht als OK markierte Daten, Netzwerkfehler und geänderte Antwortformate führen zu höchstens einem automatischen Versuch pro lokalem Kalendertag. Status: „Erneuter Versuch ausstehend“.
- Abgelehnte Zugangsdaten lösen eine erneute Anmeldung in Home Assistant aus und stoppen weitere automatische Login-Versuche.
- „Jetzt abrufen“ umgeht Abruftag und Tagesbegrenzung und fragt den derzeitigen Vormonat erneut ab. Das kann auch korrigierte Werte übernehmen.
- Der Abruftag ist über **Konfigurieren/Optionen** am Integrationseintrag änderbar.

Der letzte gültige Wert und sein Monat bleiben bei einem Fehler erhalten und werden über Neustarts hinweg gespeichert. Ein noch nicht vorhandener Wert ist unbekannt, nicht null. Die Integration importiert derzeit keine vollständige Historie: Nach mehreren Monaten Ausfall wird der aktuelle Vormonat abgefragt. Bereits erfolgreich gespeicherte Monate werden nicht automatisch auf spätere Techem-Korrekturen geprüft.

## Gas im Energie-Dashboard (ab 0.2.0)

1. Integration aktualisieren und Home Assistant neu starten.
2. **Einstellungen → Geräte & Dienste → Techem Mieterportal → Konfigurieren/Optionen** öffnen.
3. **Gasstatistik für das Energie-Dashboard** aktivieren und speichern. Die Option ist nur für Gasheizungen gedacht und standardmäßig ausgeschaltet.
4. Im Energie-Dashboard unter **Gasverbrauch → Statistik auswählen** die neue Statistik **Techem Gasverbrauch · <Adresse>** auswählen. Es ist eine externe Statistik, nicht der bisherige `sensor.heizverbrauch`. Die technische Kennung steht als Attribut `gas_statistic_id` am Heizsensor.
5. Falls der Eintrag nicht sofort erscheint, die Verarbeitung durch Recorder abwarten und die Seite neu laden. Ein erstmaliger Nullwert wird ebenfalls importiert, erzeugt aber keinen sichtbaren Verbrauchsbalken.

Der schon gespeicherte Monatswert wird beim Aktivieren direkt übernommen, ohne einen erneuten Portalabruf abzuwarten. Anschließend werden erfolgreich abgerufene Monatswerte lokal nach Monat gespeichert und in die Langzeitstatistik geschrieben. Derselbe Monat wird ersetzt statt doppelt addiert; bei einer Korrektur werden die kumulierten Summen aller folgenden gespeicherten Monate neu berechnet. Datenbank und Monatsarchiv bleiben bei Neustarts erhalten.

**Zeitliche Auflösung:** Techem liefert hier nur Monatswerte. Der gesamte Monatsverbrauch wird deshalb in der letzten Stunde des letzten Monatstags gebucht, in der bei der ersten Verwendung gespeicherten Home-Assistant-Zeitzone. Ein vorheriger Basispunkt stellt sicher, dass auch der erste Monatsverbrauch vollständig gezählt wird. Monatssummen sind so dem richtigen Monat zugeordnet. Tages- und Stundenansichten zeigen eine Monatsbuchung, keine echten Tages-/Stundenmesswerte. Es wird keine gleichmäßige Verteilung erfunden. Die Darstellung enthält weiterhin den von Techem bewerteten Heizverbrauch; dieser ist nicht automatisch identisch mit einem separaten Gaszähler am Hausanschluss.

Es werden der bereits gespeicherte Monat und zukünftige erfolgreiche Abrufe übernommen. Ein vollständiger historischer Portalabruf ist nicht Bestandteil dieses Updates. Ältere Monate werden nicht automatisch erneut bei Techem auf Korrekturen geprüft. Fehlende Monate werden nicht als gemessene Nullwerte angelegt.

Der normale Sensor bleibt **Heizverbrauch** mit dem jeweiligen Monatswert und ohne `state_class`. Die zusätzliche externe Statistik enthält `sum` in kWh und ist für die Auswahl im Energie-Dashboard vorgesehen. Der Recorder wird als Abhängigkeit geladen. Beim Deaktivieren des Schalters werden bereits importierte Statistiken nicht gelöscht; neue Importe stoppen. Entfernen der Integration löscht das lokale Monatsarchiv, nicht automatisch die Recorder-Statistik.

## Zugangsdaten und Datenzugriff

Home Assistant speichert die Zugangsdaten in seinem Konfigurationseintrag. Sie sind damit auch Teil entsprechender Home-Assistant-Backups. Der Passwortdialog ist maskiert; dies bedeutet keine zusätzliche Verschlüsselung des gespeicherten Passworts.

Jeder Abruf startet eine eigene kurzlebige Sitzung; Chrome oder ein externer Browser wird nicht benötigt. Die Sitzungs-Cookies bleiben im Arbeitsspeicher. Netzwerkanfragen, Zertifikatserstellung und Parsing laufen außerhalb des Home-Assistant-Ereignisloops in dessen Executor. HTTPS-Zertifikatsprüfung bleibt aktiv. Es gibt keine zusätzliche Python-Abhängigkeit.

Die Integration verwendet Techems regulären Login und liest strukturierte Daten aus den HTML-Seiten. Eine offiziell dokumentierte Techem-API liegt nicht zugrunde. Portaländerungen können Anpassungen erfordern. Passwort, Cookies und Antworttexte werden nicht protokolliert.

## Installation über HACS

1. In HACS das Menü **Benutzerdefinierte Repositories** öffnen.
2. `https://github.com/nothigness/techem-miterportal-homeassistant` eintragen und Kategorie **Integration** auswählen.
3. **Techem Mieterportal** herunterladen.
4. Home Assistant neu starten.
5. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach **Techem Mieterportal** suchen und Zugangsdaten sowie Abruftag eingeben.

Das Repository ist ein benutzerdefiniertes HACS-Repository; eine Aufnahme in den allgemeinen HACS-Katalog ist damit nicht verbunden. Bei einem privaten Repository benötigt HACS Zugriff über das verbundene GitHub-Konto.

## Lizenz

MIT, siehe [LICENSE](LICENSE).

## Verifikation

39 Tests bestanden gegen Home Assistant Core 2026.9.4, Python 3.14:

- Parser: gültige Nullwerte, Dezimalzahlen, fehlende/ungültige Werte, Status, Monats- und Wohnungszuordnung.
- Kalender: Jahreswechsel, Februar/Schaltjahr, verspäteter Start, Tagesbegrenzung und bereits importierter Monat.
- Einrichtung: Zugangsdatenfehler, Einzelwohnung und Wohnungsauswahl, ungültige Abruftage.
- Koordination: Speichern/Wiederherstellen, Fehler mit Beibehaltung des letzten Werts, Wiederholung und manuelles Aktualisieren, Authentifizierungsfehler.
- Echte HA-Plattformregistrierung: fünf Sensoren und ein Button, erfolgreiches Laden und Entladen.

Die HA-Tests verwenden simulierte Techem-Antworten und keine privaten Zugangsdaten. Der zugrunde liegende HTTP-Client wurde zuvor im lokalen Prototyp vom Nutzer mit seinem Konto erfolgreich getestet, einschließlich Adresse und Geschoss. Ein Live-Test der Integration in der Home-Assistant-Installation des Nutzers steht noch aus. Automatische Zeitplanung wurde simuliert, nicht über einen realen Monat beobachtet.

Tests lokal in einer passenden Python-Umgebung:

```sh
python -m pip install -r requirements-test.txt
python -m pytest -q
```

## Fehlersuche

Wenn die Integration nach dem Kopieren nicht erscheint, Ordnerstruktur prüfen und Home Assistant vollständig neu starten. Bei fehlenden Monatsdaten `consumption_month` und Abrufstatus ansehen. Nach einem Portalfehler kann „Jetzt abrufen“ erneut versuchen. Bei „Anmeldung erforderlich“ die von Home Assistant angebotene erneute Anmeldung verwenden.

Bei Änderungen des Portals keine Cookies oder Tokens öffentlich posten. Für Fehlerberichte genügen zunächst Home-Assistant-Version, Integration-Version, Abrufstatus und eine bereinigte Fehlermeldung.

## Änderungen in 0.1.1

- Abruftag als Zahlenfeld statt Slider, mit Beschriftung „Abruftag (x.ter Tag des Monats)“, auch in den Optionen.
- Gerätename: „Heizungsverbrauch <Straße und Hausnummer>“. Selbst gewählte Gerätenamen bleiben erhalten.
- Heizsensor: „Heizverbrauch“, neue Standard-ID `sensor.heizverbrauch`. Bei Namenskollisionen vergibt Home Assistant einen nummerierten Zusatz. Bekannte alte automatisch erzeugte IDs werden beim Update verkürzt; eigene IDs bleiben erhalten. Bestehende Automationen und Dashboards mit der alten ID gegebenenfalls anpassen.
- Nutzerbereitgestelltes Icon und Techem-Logo unter `brand/`; JPEG für die Anzeige in PNG konvertiert. Einbindung gemäß [Home-Assistant-Dokumentation](https://developers.home-assistant.io/docs/core/integration/brand_images/). Die Bildrechte verbleiben bei den jeweiligen Rechteinhabern; die MIT-Lizenz des Codes begründet keine Markenrechte.

Update: Inhalt von `custom_components/techem_portal` ersetzen (inklusive `brand`), Home Assistant neu starten und bei alten Bildern die Browserseite vollständig neu laden.

## Änderungen in 0.2.0

Optionale externe Gasstatistik mit rückwirkenden Monatsbuchungen, persistentem Monatsarchiv und idempotenten Datenbankimporten. Metadaten verwenden `mean_type` und `unit_class` entsprechend der aktuellen Recorder-API. Die Tests prüfen auch wiederholten Import und Wertkorrektur in einer echten Recorder-SQLite-Datenbank. Ein Live-Test im Energie-Dashboard des Nutzers steht noch aus.
