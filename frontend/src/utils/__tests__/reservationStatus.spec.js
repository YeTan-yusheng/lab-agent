import { describe, expect, it } from 'vitest'
import {
  RESERVATION_STATUS,
  actionTagType,
  actionText,
  canOwnerCancel,
  cancelHint,
  formatDateTime,
  isTerminal,
  parseStartAt,
  statusTagType,
  statusText
} from '@/utils/reservationStatus'

const now = new Date(2026, 10, 24, 10, 0)

const reservation = (overrides = {}) => ({
  status: RESERVATION_STATUS.APPROVED,
  date: '2026-11-24',
  start_time: '22:00',
  end_time: '23:00',
  ...overrides
})

describe('reservationStatus', () => {
  it('maps all statuses to text and tag types', () => {
    expect([0, 1, 2, 3, 4].map(statusText)).toEqual([
      '待审核',
      '已通过',
      '已拒绝',
      '已取消',
      '已过期'
    ])
    expect(statusTagType(0)).toBe('warning')
    expect(statusTagType(1)).toBe('success')
    expect(statusTagType(2)).toBe('danger')
    expect(statusTagType(4)).toBe('info')
  })

  it('parses start time in local timezone', () => {
    const start = parseStartAt(reservation())
    expect(start.getFullYear()).toBe(2026)
    expect(start.getMonth()).toBe(10)
    expect(start.getDate()).toBe(24)
    expect(start.getHours()).toBe(22)
    expect(start.getMinutes()).toBe(0)
  })

  it('allows pending cancellation any time', () => {
    expect(
      canOwnerCancel(reservation({ status: RESERVATION_STATUS.PENDING }), now)
    ).toBe(true)
  })

  it('uses the 12 hour boundary for approved reservations', () => {
    expect(canOwnerCancel(reservation(), now)).toBe(true)

    expect(
      canOwnerCancel(reservation({ start_time: '22:01' }), now)
    ).toBe(true)

    expect(
      canOwnerCancel(reservation({ start_time: '21:59' }), now)
    ).toBe(false)
  })

  it('rejects cancellation after start and terminal statuses', () => {
    expect(
      canOwnerCancel(
        reservation({ start_time: '09:00', end_time: '10:00' }),
        now
      )
    ).toBe(false)

    for (const status of [
      RESERVATION_STATUS.REJECTED,
      RESERVATION_STATUS.CANCELLED,
      RESERVATION_STATUS.EXPIRED
    ]) {
      expect(canOwnerCancel(reservation({ status }), now)).toBe(false)
      expect(isTerminal(status)).toBe(true)
    }
  })

  it('returns cancel hints only when cancellation is unavailable', () => {
    expect(
      cancelHint(reservation({ status: RESERVATION_STATUS.PENDING }), now)
    ).toBe('')
    expect(cancelHint(reservation({ start_time: '21:59' }), now)).toContain(
      '12 小时'
    )
    expect(
      cancelHint(reservation({ status: RESERVATION_STATUS.EXPIRED }), now)
    ).toContain('不可取消')
  })

  it('maps history actions and formats timestamps', () => {
    expect(actionText('force_cancel')).toBe('强制取消')
    expect(actionText('submit')).toBe('提交')
    expect(actionTagType('approve')).toBe('success')
    expect(formatDateTime('2026-11-24T10:00:00')).not.toBe('-')
    expect(formatDateTime(null)).toBe('-')
  })
})