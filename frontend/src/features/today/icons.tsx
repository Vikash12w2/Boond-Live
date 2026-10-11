// Small glyphs used only by the Today hero. Action icons live in src/actions.tsx.

export function SpeakerIcon({ playing }: { playing: boolean }) {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {playing ? (
        <rect x="6" y="6" width="12" height="12" rx="1.5" fill="currentColor" />
      ) : (
        <>
          <path d="M3.5 9.5h3.5L12 5v14l-5-4.5H3.5z" fill="currentColor" />
          <path
            d="M15.5 9a4.2 4.2 0 0 1 0 6M18.3 6.3a8 8 0 0 1 0 11.4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </>
      )}
    </svg>
  )
}

export function CloudOffIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" focusable="false">
      <path d="M7 17.5a4 4 0 0 1-.6-8 5.5 5.5 0 0 1 10.6 1.3A3.4 3.4 0 0 1 17 17.5z" />
      <path d="M12 9.5v3.5M12 15.6v.1" />
    </svg>
  )
}
