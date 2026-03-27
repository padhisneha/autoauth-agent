import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/dashboard/stats`);
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    // Return safe defaults so UI doesn't crash on null
    return NextResponse.json({
      total_requests: 0,
      approved: 0,
      denied: 0,
      pending: 0,
      approval_rate: 0,
      avg_processing_time_seconds: 0,
      total_cost_saved: 0,
      appeals_success_rate: 0,
    });
  }
}