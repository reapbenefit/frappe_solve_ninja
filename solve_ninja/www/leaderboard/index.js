frappe.ready(function() {
		reset_limit_and_start()
		// setup_leaderboad_html(get_filters())
		get_users(get_filters())
		$("#search").click(()=>{
			reset_limit_and_start()
			get_users(get_filters())
		})
		$("#clear").click(()=>{
			reset_limit_and_start()
			clear_filters()
			get_users()
		})
		$("#rank-based-on").change(()=>{
			reset_limit_and_start()
			get_users(get_filters())
		})
		$("#ninja").keyup(function(event) {
			if (event.keyCode === 13) {
				$("#search").click();
			}
		});
		$("#btn_load_more").click(()=>{ 
			get_users(get_filters())
		})
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

var setup_leaderboad_html = function(filters) {
	let html = '';
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
			<tbody id="ninja-table">
			</tbody>
			</table>
		</div>`
	$("#Ranktable").html(html)
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
						"filters": filters,
						"page_length": frappe.flags.leader_page_length,
                		"start": frappe.flags.leader_start,
				},
				freeze: true,
				freeze_message: "...Searcing Users",
				callback: function(result) {
					if (frappe.flags.leader_start == 0) {
						setup_leaderboad_html(get_filters())
					}
					if (result.message.length > 0) {
						let html_ = ``
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
								html_ += `<tr class="ninja-row">
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
							$("#ninja-table").append(html_)
							frappe.flags.leader_page_length = 20
						}
						
						else if(frappe.flags.leader_start == 0) {
							html=`<div class="container">
								<div class="no-record">
									No Record Found
								</div>
							</div>`
							$("#Ranktable").html(html)
						}
					frappe.flags.leader_start = $('.ninja-row').length
				}
		});
}
var reset_limit_and_start = function(){
	frappe.flags.leader_page_length = 10
	frappe.flags.leader_start = 0
}
