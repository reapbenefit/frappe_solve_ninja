frappe.ready(function() {
		get_users(get_filters())
		$("#search").click(()=>{
			get_users(get_filters())
		})
		$("#clear").click(()=>{
			clear_filters()
			get_users()
		})
		$("#rank-based-on").change(()=>{
			get_users(get_filters())
		})
		$("#ninja").keyup(function(event) {
			if (event.keyCode === 13) {
				$("#search").click();
			}
		});
		$(".contribute-button").click(()=>{
			if (navigator.doNotTrack != 1 && !window.is_404) {
				let browser = frappe.utils.get_browser();
				frappe.call("frappe.website.doctype.web_page_view.web_page_view.make_view_log", {
					path: "contribute",
					referrer: null,
					browser: browser.name,
					version: browser.version,
					url: location.origin,
					user_tz: Intl.DateTimeFormat().resolvedOptions().timeZone
				})
			}
			window.open("http://wa.me/918095500118?text=cmp")
		})
});

var get_filters = function() {
		return {
			"ninja": $("#ninja").val(),
			"organization": $("#organization").val(),
			"city": $("#city").val(),
			"hr_range": $("#hr-range").val(),
			"recent_rank_based_on": $("#rank-based-on").val(),
		}
};

var clear_filters = function() {
	$("#ninja").val("")
	$("#organization").val("")
	$("#city").val("")
	$("#rank-based-on").val("")
	$("#hr-range").val("")
}
var get_users = function(filters={}) {
		let rank_img = {
			1: "files/rank-1.png",
			2: "files/rank-2.png",
			3: "files/rank-3.png",
		}

		let org_based = 0
		const urlParams = new URLSearchParams(window.location.search);
		if (urlParams.get("org")) {
			filters["organization"] = urlParams.get("org")
		}

		frappe.call({
				method: "solve_ninja.api.leaderboard.search_users_",
				args: {
						"filters": filters
				},
				freeze: true,
				freeze_message: "...Searcing Users",
				callback: function(result) {
					let html = '';
						if (result.message.length > 0) {
							let rrh = ["Last Month", "Last 15 Days"].includes(filters.recent_rank_based_on) ? "<th>Recent Rank</th>" : "" 
							html = `<div class="container">
								<table class="table table-striped" style="text-align: center">
									<thead>
										<tr>
											<th>Overall Rank</th>
											${rrh}
											<th class="text-left">Name</th>
											<th class="text-left">City</th>
											<th class="text-right">Hours</th>
											<th class="text-right">Actions</th>
										</tr>
									</thead>
									<tbody>`
								result.message.forEach(leader => {
									let rank = leader.rank ? leader.rank : "";
									if (rank){
										if(rank_img[rank]) {
											rank = `<img src="${rank_img[rank]}" style="height: 42px" />`;
										}
									}
									let city = leader.city ? leader.city : "";
									let rr = leader.recent_rank ? leader.recent_rank : leader.rank;
									let rrh = ["Last Month", "Last 15 Days"].includes(filters.recent_rank_based_on) ? `<td>${rr}</td>` : "" 
									html += `<tr>
									<td>
										<div>
											<span class="name-rank">${rank}</span>
										</div>
									</td>
									${rrh}
									<td class="text-left" style="vertical-align: middle">
										<a href="/user-profile/${leader.username}" class="name-rank">${leader.full_name}</a>
									</td>
					
									<td class="text-left" style="vertical-align: middle">${city}</td>
									<td class="text-right" style="vertical-align: middle">${leader.hours_invested}</td>
									<td class="text-right" style="vertical-align: middle">${leader.contribution_count}</td>
								</tr>`
							});
							html += `</tbody>
								</table>
							</div>`
							$("#Ranktable").html(html)
						}
						
						else {
							html=`<div class="container">
								<div class="no-record">
									No Record Found
								</div>
							</div>`
							$("#Ranktable").html(html)
						}
				}
		});
}
