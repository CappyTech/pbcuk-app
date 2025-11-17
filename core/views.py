from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from quotes.models import Quote


def index(request):

	# Ensure a session exists for tracking and reservation ownership
	if not request.session.session_key:
		request.session.save()
	session_key = request.session.session_key

	# Visited quotes
	visited_tokens = request.session.get('visited_quote_tokens', [])
	visited = list(Quote.objects.filter(token__in=visited_tokens)) if visited_tokens else []
	visited_public = [q for q in visited if q.is_public]
	visited_private = [q for q in visited if not q.is_public]

	# Active reservations window
	cutoff = timezone.now() - timedelta(minutes=Quote.RESERVATION_DURATION)

	# Public browse list: hide quotes reserved by other sessions (but keep mine visible)
	public_quotes = (
		Quote.objects.filter(is_public=True)
		.exclude(Q(reservation_started_at__gte=cutoff) & ~Q(reservation_session_key=session_key))
		.order_by('-created_at')
	)

	# Badge counts for all public quotes (regardless of visibility), split by availability
	all_public_qs = Quote.objects.filter(is_public=True)
	public_reserved_count = all_public_qs.filter(reservation_started_at__gte=cutoff).count()
	public_available_count = all_public_qs.exclude(reservation_started_at__gte=cutoff).count()
	reserved_my = Quote.objects.filter(
		reservation_session_key=session_key,
		reservation_started_at__gte=cutoff,
	).order_by('-reservation_started_at')

	context = {
		'quotes': public_quotes,
		'visited_public': visited_public,
		'visited_private': visited_private,
		'reserved_my': reserved_my,
		'public_reserved_count': public_reserved_count,
		'public_available_count': public_available_count,
	}
	return render(request, 'core/home.html', context)

# Create your views here.
