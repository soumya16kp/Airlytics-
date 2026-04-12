import React from 'react';
import { NavLink } from 'react-router-dom';
import './Navbar.css';

/*
 * Custom SVG icons for each pollutant.
 * Each icon is designed to visually represent the properties of its gas:
 *   CO  — Smoke/exhaust cloud (silent, odorless killer from combustion)
 *   NO₂ — Factory chimney with emissions (industrial/combustion source)
 *   SO₂ — Acid rain cloud with droplets (primary cause of acid rain)
 *   O₃  — Sun with protective shield arc (ozone layer / UV protection)
 */

const COIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Smoke/exhaust wisps representing silent poisonous CO gas */}
    <path
      d="M4 18c0-2.21 1.79-4 4-4h1c.55 0 1-.45 1-1s.45-1 1-1h1c1.66 0 3 1.34 3 3s-1.34 3-3 3H8c-2.21 0-4-1.79-4-4z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M12 15h4c1.66 0 3-1.34 3-3s-1.34-3-3-3h-1c-.55 0-1 .45-1 1"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    {/* Rising smoke wisps */}
    <path
      d="M8 10c0-1 .5-2 1.5-2.5"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinecap="round"
      opacity="0.7"
    />
    <path
      d="M14 7c0-1.5 1-2.5 2-3"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinecap="round"
      opacity="0.5"
    />
    <path
      d="M10 5c.5-1 1.5-1.5 2-2"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinecap="round"
      opacity="0.4"
    />
  </svg>
);

const NO2Icon = () => (
  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Factory/industrial chimney — NO₂ comes from combustion & industry */}
    {/* Building base */}
    <rect
      x="3"
      y="14"
      width="18"
      height="7"
      rx="1"
      stroke="currentColor"
      strokeWidth="1.5"
    />
    {/* Chimney stacks */}
    <rect
      x="6"
      y="8"
      width="3"
      height="6"
      stroke="currentColor"
      strokeWidth="1.5"
    />
    <rect
      x="13"
      y="10"
      width="3"
      height="4"
      stroke="currentColor"
      strokeWidth="1.5"
    />
    {/* Smoke from chimneys */}
    <path
      d="M7.5 8c-.5-1.5 0-3 1-3.5"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinecap="round"
      opacity="0.7"
    />
    <path
      d="M14.5 10c.5-1.5 0-2.5-.8-3"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinecap="round"
      opacity="0.6"
    />
    <path
      d="M9 7c.3-1 1-2 1.5-2.5"
      stroke="currentColor"
      strokeWidth="1"
      strokeLinecap="round"
      opacity="0.4"
    />
    {/* Windows */}
    <circle cx="8" cy="17.5" r="0.8" fill="currentColor" opacity="0.5" />
    <circle cx="12" cy="17.5" r="0.8" fill="currentColor" opacity="0.5" />
    <circle cx="16" cy="17.5" r="0.8" fill="currentColor" opacity="0.5" />
  </svg>
);

const SO2Icon = () => (
  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Acid rain cloud — SO₂ is the primary cause of acid rain */}
    {/* Cloud body */}
    <path
      d="M6 16a3 3 0 0 1-.2-6A5 5 0 0 1 16 10h.5a3.5 3.5 0 0 1 .5 7H6z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    {/* Acid rain droplets */}
    <path
      d="M8 19v2"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      opacity="0.8"
    />
    <path
      d="M12 19v2.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      opacity="0.6"
    />
    <path
      d="M16 19v1.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      opacity="0.7"
    />
    {/* Warning indicator on cloud */}
    <path
      d="M11 10l1-2 1 2"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      opacity="0.6"
    />
    <line
      x1="12" y1="12.5" x2="12" y2="11.5"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinecap="round"
      opacity="0.5"
    />
  </svg>
);

const O3Icon = () => (
  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Sun with protective shield arc — O₃ ozone layer protects from UV */}
    {/* Sun core */}
    <circle
      cx="12"
      cy="12"
      r="3.5"
      stroke="currentColor"
      strokeWidth="1.5"
    />
    {/* Sun rays */}
    <line x1="12" y1="2" x2="12" y2="5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="12" y1="19" x2="12" y2="22" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="2" y1="12" x2="5" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="19" y1="12" x2="22" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    {/* Diagonal rays */}
    <line x1="4.93" y1="4.93" x2="6.76" y2="6.76" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity="0.7" />
    <line x1="17.24" y1="17.24" x2="19.07" y2="19.07" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity="0.7" />
    <line x1="19.07" y1="4.93" x2="17.24" y2="6.76" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity="0.7" />
    <line x1="6.76" y1="17.24" x2="4.93" y2="19.07" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity="0.7" />
    {/* Protective shield arc (ozone layer) */}
    <path
      d="M5 5.5a10 10 0 0 1 14 0"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      opacity="0.5"
      strokeDasharray="3 2"
    />
  </svg>
);

const pollutants = [
  {
    key: 'co',
    path: '/dashboard/co',
    formula: <span className="pollutant-formula">CO</span>,
    name: 'Carbon Monoxide',
    Icon: COIcon,
  },
  {
    key: 'no2',
    path: '/dashboard/no2',
    formula: <span className="pollutant-formula">NO<sub>2</sub></span>,
    name: 'Nitrogen Dioxide',
    Icon: NO2Icon,
  },
  {
    key: 'so2',
    path: '/dashboard/so2',
    formula: <span className="pollutant-formula">SO<sub>2</sub></span>,
    name: 'Sulfur Dioxide',
    Icon: SO2Icon,
  },
  {
    key: 'o3',
    path: '/dashboard/o3',
    formula: <span className="pollutant-formula">O<sub>3</sub></span>,
    name: 'Ozone',
    Icon: O3Icon,
  },
];

const Navbar = () => {
  return (
    <nav className="pollutant-navbar-wrapper" id="pollutant-navbar">
      <div className="pollutant-nav-links">
        {pollutants.map(({ key, path, formula, name, Icon }) => (
          <NavLink
            key={key}
            to={path}
            className={({ isActive }) =>
              `pollutant-nav-link ${isActive ? 'active' : ''}`
            }
            id={`nav-${key}`}
          >
            <span className="pollutant-icon">
              <Icon />
            </span>
            {formula}
            <span className="pollutant-name">{name}</span>
            <span className="pollutant-live-dot" />
          </NavLink>
        ))}
      </div>
    </nav>
  );
};

export default Navbar;
