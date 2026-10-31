import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'

/**
 * First-run guided tour (Next/Back/Skip) anchored to `data-tour`
 * attributes in the request view. Steps reference anchors, never
 * component internals, so view refactors only break the tour if an
 * anchor is removed — and the tour skips missing anchors gracefully
 * instead of crashing.
 */

const TOUR_SEEN_KEY = 'iam-tour-seen-v1'

export function hasSeenTour(): boolean {
  try {
    return localStorage.getItem(TOUR_SEEN_KEY) === '1'
  } catch {
    return true
  }
}

function markTourSeen(): void {
  try {
    localStorage.setItem(TOUR_SEEN_KEY, '1')
  } catch {
    // Private mode — the tour just shows again next time.
  }
}

export function resetTourSeen(): void {
  try {
    localStorage.removeItem(TOUR_SEEN_KEY)
  } catch {
    // ignore
  }
}

export function launchTour(): void {
  const tour = driver({
    showProgress: true,
    showButtons: ['next', 'previous', 'close'],
    popoverClass: 'iam-tour-popover',
    onDestroyed: markTourSeen,
    steps: [
      {
        element: '[data-tour="request-input"]',
        popover: {
          title: 'Describe the job, not the permissions',
          description:
            'Say what you are trying to accomplish — e.g. "investigate incident 501 in the orders table". The AI figures out the IAM actions.',
        },
      },
      {
        element: '[data-tour="guided-fields"]',
        popover: {
          title: 'Stuck? Fill in the blanks',
          description:
            'Task, resources, and ticket fields help when you cannot articulate the full request. Anything you skip, the assistant will ask about.',
        },
      },
      {
        element: '[data-tour="request-duration"]',
        popover: {
          title: 'How long do you need it?',
          description:
            'Credentials expire automatically. Higher-risk grants get shorter maximum durations.',
        },
      },
      {
        element: '[data-tour="request-submit"]',
        popover: {
          title: 'Generate the policy',
          description:
            'Review the least-privilege policy, the plain-language summary, and any guardrail findings before issuing credentials.',
        },
      },
      {
        popover: {
          title: "You're ready",
          description:
            'Press ? any time for keyboard shortcuts, or open Help for guides, update status, and your audit log.',
        },
      },
    ],
  })
  tour.drive()
}
