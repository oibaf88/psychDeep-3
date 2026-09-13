import { Link } from "react-router-dom";

export default function SharingPage() {
  return (
    <div className="page">
      <h1>Compartir</h1>
      <p className="subtitle">Tú controlas qué finalidades autorizas y qué profesional puede acceder a tu seguimiento.</p>

      <section className="card">
        <h2>Profesionales vinculados</h2>
        <p>Revisa solicitudes, acepta o termina vinculaciones. Una vinculación no da acceso global fuera de su ámbito.</p>
        <Link className="btn-secondary" to="/assignments">Gestionar vinculaciones</Link>
      </section>

      <section className="card">
        <h2>Consentimientos</h2>
        <p>Gestiona por separado el procesamiento básico, el análisis lingüístico, compartir con profesionales, comunicaciones de crisis e investigación/mejora del modelo.</p>
        <Link className="btn-secondary" to="/consents">Gestionar consentimientos</Link>
      </section>

      <section className="card">
        <h2>Preparar consulta</h2>
        <p>Tu historial, tendencias y hechos confirmados permanecen separados de las inferencias. Puedes revisar y corregir interpretaciones antes de usarlas en una consulta.</p>
        <div className="alert-actions">
          <Link className="btn-secondary" to="/trends">Ver tendencias</Link>
          <Link className="btn-secondary" to="/facts">Revisar hechos</Link>
        </div>
      </section>
    </div>
  );
}
