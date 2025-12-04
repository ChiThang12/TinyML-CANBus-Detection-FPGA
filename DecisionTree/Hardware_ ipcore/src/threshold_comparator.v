module threshold_comparator (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_in,
    input  wire [31:0] feature_value,
    input  wire [26:0] threshold_raw,
    output reg         go_left,
    output reg         valid_out
);

    wire [31:0] threshold_extended;
    assign threshold_extended = {5'b0, threshold_raw};
    
    // Pipeline comparison để cải thiện timing
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            go_left <= 1'b0;
            valid_out <= 1'b0;
        end else if (valid_in) begin
            go_left <= (feature_value <= threshold_extended);
            valid_out <= 1'b1;
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule
