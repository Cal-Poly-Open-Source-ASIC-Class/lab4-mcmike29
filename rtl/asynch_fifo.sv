module asynch_fifo #(
    parameter AW = 4, //Address width 2^AW
    parameter DW = 8 // Data width
)(
    input wire clk_w,
    input wire rst_w,
    input wire w_en,
    input wire [DW-1:0] w_data,
    output reg full,

    input wire clk_r,
    input wire rst_r,
    input wire r_en,
    output wire [DW-1:0] r_data,
    output reg empty
);

    // Memory array
    reg [DW-1:0] mem [0:(1<<AW)-1];

    // Binary and Gray-coded pointers
    reg [AW:0] wbin, wgray;
    reg [AW:0] rbin, rgray;

    // Synchronized gray pointers across clock domains
    reg [AW:0] rq1_wgray, rq2_wgray; // read domain-synced write gray pointers
    reg [AW:0] wq1_rgray, wq2_rgray; // write domain-synced read gray pointers

    reg [DW-1:0] r_data_reg;
    assign r_data = r_data_reg;


    // Write-side logic   
    wire [AW:0] wbin_next = wbin + {{AW{1'b0}}, (w_en && !full)};
    wire [AW:0] wgray_next = (wbin_next >> 1) ^ wbin_next;
    wire [AW-1:0] waddr = wbin[AW-1:0]; // <- current wbin value

    always @(posedge clk_w or negedge rst_w) begin
        if (!rst_w) begin
            wbin  <= 0;
            wgray <= 0;
        end 
        else begin
            if (w_en && !full) begin
                mem[waddr] <= w_data;
                wbin  <= wbin_next;
                wgray <= wgray_next; // (wbin_next >> 1) ^ wbin_next;
            end
        end
    end

    // Synchronize read pointer into write domain
    always @(posedge clk_w or negedge rst_w) begin
        if (!rst_w)
            {wq2_rgray, wq1_rgray} <= 0;
        else
            {wq2_rgray, wq1_rgray} <= {wq1_rgray, rgray};
    end

    wire full_cond = (wgray_next[AW:AW-1] == ~wq2_rgray[AW:AW-1]) && (wgray_next[AW-2:0] == wq2_rgray[AW-2:0]);

    always @(posedge clk_w or negedge rst_w) begin
        if (!rst_w)
            full <= 1'b0;
        else
            full <= full_cond;
    end


    // Read-side logic
    wire [AW:0] rbin_next = rbin + {{AW{1'b0}}, (r_en && !empty)};
    wire [AW:0] rgray_next = (rbin_next >> 1) ^ rbin_next;
    wire [AW-1:0] raddr = rbin[AW-1:0];

    always @(posedge clk_r or negedge rst_r) begin
        if (!rst_r) begin
            rbin <= 0;
            rgray <= 0;
            r_data_reg <= 0;
        end
        else if (r_en && !empty) begin
            r_data_reg <= mem[raddr];
            rbin <= rbin_next;
            rgray <= rgray_next;
        end
    end



    // Synchronize write pointer into read domain
    always @(posedge clk_r or negedge rst_r) begin
        if (!rst_r)
            {rq2_wgray, rq1_wgray} <= 0;
        else
            {rq2_wgray, rq1_wgray} <= {rq1_wgray, wgray};
    end

    // Empty detection
    wire empty_cond = (rgray == rq2_wgray);

    always @(posedge clk_r or negedge rst_r) begin
        if (!rst_r)
            empty <= 1'b1;
        else
            empty <= empty_cond;
    end
		
endmodule